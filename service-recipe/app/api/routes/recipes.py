from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.http_client import (
    ServicesUserClient,
    get_user_client,
    ServiceUnavailableError,
)
from app.db.session import get_session
from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe import (
    RecipeCreate,
    RecipeResponse,
    RecipeUpdate,
    PaginatedRecipeResponse,
    RecipeManualCreate,
    ImageSearchRequest,
    ImageSelectRequest,
)
from app.i18n import LocalizedHTTPException
from app.services.search_service import search_service
from app.services.recipe_service import RecipeService
from app.services.storage_service import StorageService
from app.core.config import settings
from app.core.deps import get_current_user_id, require_admin


router = APIRouter()


class RecipeServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> RecipeService:
        return RecipeService(RecipeRepository(session), search_service)


class StorageServiceFactory:
    @staticmethod
    def inject() -> StorageService:
        return StorageService(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            public_url=settings.MINIO_PUBLIC_URL,
        )


@router.put("/id/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdate,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    return await service.update(recipe_id, recipe_data, current_user_id)


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe_data: RecipeCreate,
    request: Request,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    user_client: ServicesUserClient = Depends(get_user_client),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    try:
        exists = await user_client.user_exist(current_user_id)
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_user_unavailable(request)
    if not exists:
        raise LocalizedHTTPException.user_id_not_exists(request)

    return await service.create(recipe_data, current_user_id)


@router.get("", response_model=PaginatedRecipeResponse)
async def list_recipes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    course_type: str | None = Query(None),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> PaginatedRecipeResponse:
    """List recipes with optional course_type filter and pagination."""
    return await service.list_recipes(page, page_size, course_type)


@router.get("/counts-by-user", response_model=dict[str, int])
async def counts_by_user(
    _admin: dict = Depends(require_admin),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> dict[str, int]:
    """Return {user_id: recipe_count} for all authors. Admin-only."""
    return await service.counts_by_user()


@router.get("/{slug}", response_model=RecipeResponse)
async def get_recipe_by_slug(
    slug: str,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> RecipeResponse:
    """get recipe by slug"""
    return await service.get_by_slug(slug)


@router.get("/id/{id}", response_model=RecipeResponse)
async def get_recipe_by_id(
    id: int,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> RecipeResponse:
    """get recipe by id"""
    return await service.get_by_id(id)


@router.delete("/id/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> None:
    await service.delete(recipe_id, current_user_id)


@router.post(
    "/manual", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED
)
async def create_recipe_manual(
    recipe_data: RecipeManualCreate,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    return await service.create_manual(recipe_data, current_user_id)


@router.post("/id/{recipe_id}/image", response_model=RecipeResponse)
async def upload_recipe_image(
    recipe_id: int,
    file: UploadFile = File(...),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    storage: StorageService = Depends(StorageServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    try:
        image_url = await storage.upload_image(data, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return await service.update_image_url(
        recipe_id, user_id=current_user_id, image_url=image_url
    )


@router.post("/id/{recipe_id}/image-suggestions", response_model=RecipeResponse)
async def refresh_image_suggestions(
    recipe_id: int,
    body: ImageSearchRequest,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    """Relance une recherche Unsplash avec un mot-clé libre et renvoie 4 propositions."""
    return await service.refresh_suggestions(recipe_id, body.keyword, current_user_id)


@router.post("/id/{recipe_id}/image/select", response_model=RecipeResponse)
async def select_recipe_image(
    recipe_id: int,
    body: ImageSelectRequest,
    service: RecipeService = Depends(RecipeServiceFactory.inject),
    current_user_id: str = Depends(get_current_user_id),
) -> RecipeResponse:
    """Valide et enregistre l'image finale choisie parmi les propositions Unsplash."""
    return await service.select_image(recipe_id, body.unsplash_id, current_user_id)


@router.post("/reindex", status_code=status.HTTP_200_OK)
async def reindex_recipes(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_current_user_id),
):
    """Reindex all recipes into Elasticsearch."""
    count = await search_service.reindex_all(session)
    return {"indexed": count}
