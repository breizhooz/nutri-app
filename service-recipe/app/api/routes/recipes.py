import json

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
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
from app.schemas.recipe_import import (
    RecipeImportPayload,
    ImportEnqueueResponse,
    ImportTaskStatus,
)
from app.services.search_service import search_service
from app.services.recipe_service import RecipeService
from app.services.import_task_service import ImportTaskService
from app.services.storage_service import StorageService
from app.core.config import settings
from app.core.deps import get_current_user_id, require_admin
from celery_app import celery_app


router = APIRouter()


class RecipeServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> RecipeService:
        return RecipeService(RecipeRepository(session), search_service)


class ImportTaskServiceFactory:
    @staticmethod
    def inject() -> ImportTaskService:
        return ImportTaskService(celery_app)


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
    created_by_user_id: str | None = Query(None),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> PaginatedRecipeResponse:
    """List recipes with optional course_type / author filters and pagination."""
    return await service.list_recipes(page, page_size, course_type, created_by_user_id)


@router.get("/counts-by-user", response_model=dict[str, int])
async def counts_by_user(
    _admin: dict = Depends(require_admin),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> dict[str, int]:
    """Return {user_id: recipe_count} for all authors. Admin-only."""
    return await service.counts_by_user()


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ImportEnqueueResponse,
)
async def import_recipes(
    request: Request,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
    import_task_service: ImportTaskService = Depends(ImportTaskServiceFactory.inject),
    user_client: ServicesUserClient = Depends(get_user_client),
) -> ImportEnqueueResponse:
    """Bulk import recipes (+ ingredient catalog) from a JSON file. Admin-only.

    Le fichier est validé immédiatement (JSON + schéma + existence du
    ``created_by_user_id`` auprès de service-user) puis l'import — long car il
    appelle service-nutrition pour chaque recette — est délégué à une tâche Celery.
    Renvoie un ``task_id`` à suivre via ``GET /import/{task_id}``. Même format que
    scripts/import_recipes.py : les recettes sont attribuées au
    ``created_by_user_id`` porté par le fichier.
    """
    raw_bytes = await file.read()
    try:
        raw = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LocalizedHTTPException.import_invalid_json(request, str(exc))

    try:
        payload = RecipeImportPayload.model_validate(raw)
    except ValidationError as exc:
        raise LocalizedHTTPException.import_validation_failed(request, str(exc))

    # Refuse d'attribuer les recettes à un user fantôme : on vérifie que le
    # created_by_user_id du fichier correspond à un compte réel (évite les
    # recettes orphelines qui n'apparaissent chez personne).
    try:
        exists = await user_client.user_exist(payload.created_by_user_id)
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_user_unavailable(request)
    if not exists:
        raise LocalizedHTTPException.user_id_not_exists(request)

    # On transmet le payload re-sérialisé (JSON-safe : enums → valeurs) au worker,
    # ainsi que l'id de l'admin déclencheur (notifié en fin/échec d'import).
    task_id = await run_in_threadpool(
        import_task_service.enqueue,
        payload.model_dump(mode="json"),
        str(admin["sub"]),
    )
    return ImportEnqueueResponse(task_id=task_id)


@router.get("/import/{task_id}", response_model=ImportTaskStatus)
async def import_status(
    task_id: str,
    _admin: dict = Depends(require_admin),
    import_task_service: ImportTaskService = Depends(ImportTaskServiceFactory.inject),
) -> ImportTaskStatus:
    """État d'une tâche d'import (polling du front). Admin-only.

    Sur succès, ``result`` porte le rapport
    ({ingredients_upserted, recipes_created, recipe_slugs}).
    """
    return await run_in_threadpool(import_task_service.task_status, task_id)


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


@router.delete("/by-user/{user_id}", status_code=status.HTTP_200_OK)
async def delete_recipes_by_user(
    user_id: str,
    _admin: dict = Depends(require_admin),
    service: RecipeService = Depends(RecipeServiceFactory.inject),
) -> dict[str, int]:
    """Delete every recipe authored by a user and unindex them. Admin-only."""
    deleted = await service.delete_by_user(user_id)
    return {"deleted": deleted}


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
    image_url = await storage.upload_image(data, content_type)
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
