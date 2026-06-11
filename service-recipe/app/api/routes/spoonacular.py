from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from nutri_shared.core.context import AccessContext

from app.core.deps import get_current_user_id, get_write_context
from app.db.session import get_session
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.spoonacular_cache_repository import SpoonacularCacheRepository
from app.schemas.recipe import RecipeResponse
from app.schemas.spoonacular import SpoonacularShakeResponse
from app.services.recipe_service import RecipeService
from app.services.search_service import search_service
from app.services.spoonacular_cache_service import SpoonacularCacheService
from app.services.spoonacular_mapper import short_description

router = APIRouter()


class SpoonacularCacheServiceFactory:
    @staticmethod
    def inject(
        session: AsyncSession = Depends(get_session),
    ) -> SpoonacularCacheService:
        return SpoonacularCacheService(SpoonacularCacheRepository(session))


class RecipeServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> RecipeService:
        return RecipeService(RecipeRepository(session), search_service)


@router.get("/shake", response_model=SpoonacularShakeResponse)
async def shake_recipe(
    service: SpoonacularCacheService = Depends(
        SpoonacularCacheServiceFactory.inject
    ),
    _user: str = Depends(get_current_user_id),
) -> SpoonacularShakeResponse:
    """« Shake ta recette » : une recette du cache Spoonacular tirée au hasard.

    404 (recette non trouvée) si le cache est encore vide.
    """
    recipe = await service.get_random()
    payload = recipe.payload or {}
    return SpoonacularShakeResponse(
        spoonacular_id=recipe.spoonacular_id,
        title=recipe.title,
        description=short_description(payload),
        image_url=recipe.image_url,
        source_url=recipe.source_url,
        payload=payload,
    )


@router.post(
    "/{spoonacular_id}/add",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_personal_list(
    spoonacular_id: int,
    service: SpoonacularCacheService = Depends(
        SpoonacularCacheServiceFactory.inject
    ),
    recipe_service: RecipeService = Depends(RecipeServiceFactory.inject),
    ctx: AccessContext = Depends(get_write_context),
) -> RecipeResponse:
    """Ajoute la recette Spoonacular à la liste personnelle du compte actif.

    Passe par le pipeline habituel (``create_full``) : hydratation des
    ingrédients, calcul des macros (service-nutrition), indexation Elasticsearch.
    """
    return await service.add_to_personal_list(
        spoonacular_id, ctx.sub, ctx.account_id, recipe_service
    )
