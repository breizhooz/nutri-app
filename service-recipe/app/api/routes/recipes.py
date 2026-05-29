from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from elasticsearch import NotFoundError

from app.core.http_client import (
    ServicesUserClient,
    get_user_client,
    ServiceUnavailableError,
)
from app.db.session import get_session
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
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
from app.core.utils import slugify
from app.i18n import LocalizedHTTPException
from app.i18n.loader import t
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


async def _load_with_relations(session: AsyncSession, recipe_id: int):
    """
    Load a recipe with ingredients (eager load required in async SQLAlchemy).
    """
    result = await session.execute(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(
                RecipeIngredient.ingredient
            )
        )
    )

    return result.scalar_one_or_none()


@router.put("/id/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    if (
        recipe.created_by_user_id is None
        or str(recipe.created_by_user_id) != current_user_id
    ):
        raise LocalizedHTTPException.unauthorized(request)

    update_fields = recipe_data.model_dump(
        exclude_unset=True, exclude={"recipe_ingredients"}
    )

    # renew the slug if change title
    if "title" in update_fields:
        new_slug = slugify(update_fields["title"])
        conflict = await session.execute(
            select(Recipe).where(Recipe.slug == new_slug, Recipe.id != recipe_id)
        )
        if conflict.scalar_one_or_none():
            i = 1
            while True:
                if i > 100:
                    raise LocalizedHTTPException.slug_too_big(request)
                candidate = f"{new_slug} - {i}"
                conflict = await session.execute(
                    select(Recipe).where(
                        Recipe.slug == candidate, Recipe.id != recipe_id
                    )
                )
                if not conflict.scalar_one_or_none():
                    new_slug = candidate
                    break
                i += 1
        update_fields["slug"] = new_slug

    for field, value in update_fields.items():
        setattr(recipe, field, value)

    if recipe_data.recipe_ingredients is not None:
        await session.execute(
            delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
        )
        for ing_data in recipe_data.recipe_ingredients:
            session.add(
                RecipeIngredient(
                    recipe_id=recipe_id,
                    ingredient_id=ing_data.ingredient_id,
                    quantity=ing_data.quantity,
                    unit=ing_data.unit,
                )
            )

    await session.commit()

    recipe_with_relations = await _load_with_relations(session, recipe_id)
    recipe_to_return = (
        recipe_with_relations if recipe_with_relations is not None else recipe
    )

    try:
        await search_service.index_recipe(recipe_to_return)
    except Exception as e:
        locale = getattr(request.state, "locale", "fr")
        print(
            f"{t.get('elasticsearch.errors.update_indexation_for_recipe', locale=locale)} : {recipe_id} : {e}"
        )

    return recipe_to_return


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
    session: AsyncSession = Depends(get_session),
):
    """List recipes with optional course_type filter and pagination."""
    base_query = select(Recipe)
    count_query = select(func.count()).select_from(Recipe)

    if course_type:
        base_query = base_query.where(Recipe.course_type == course_type)
        count_query = count_query.where(Recipe.course_type == course_type)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    items_result = await session.execute(
        base_query.options(
            selectinload(Recipe.recipe_ingredients).selectinload(
                RecipeIngredient.ingredient
            )
        )
        .order_by(Recipe.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(items_result.scalars().all())

    pages = max(1, -(-total // page_size))  # ceiling division
    return PaginatedRecipeResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.get("/counts-by-user", response_model=dict[str, int])
async def counts_by_user(
    _admin: dict = Depends(require_admin),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> dict[str, int]:
    """Return {user_id: recipe_count} for all authors. Admin-only."""
    return await service.counts_by_user()


@router.get("/{slug}", response_model=RecipeResponse)
async def get_recipe_by_slug(
    slug: str, request: Request, session: AsyncSession = Depends(get_session)
):
    """get recipe by slug"""
    result = await session.execute(
        select(Recipe)
        .where(Recipe.slug == slug)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(
                RecipeIngredient.ingredient
            )
        )
    )
    recipe = result.scalar_one_or_none()

    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    return recipe


@router.get("/id/{id}", response_model=RecipeResponse)
async def get_recipe_by_id(
    id: int, request: Request, session: AsyncSession = Depends(get_session)
):
    """get recipe by id"""
    recipe = await _load_with_relations(session, id)

    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    return recipe


@router.delete("/id/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    if (
        recipe.created_by_user_id is None
        or str(recipe.created_by_user_id) != current_user_id
    ):
        raise LocalizedHTTPException.unauthorized(request)

    await session.delete(recipe)
    await session.commit()

    try:
        await search_service.delete_recipe(recipe_id)
    except NotFoundError:
        pass


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
