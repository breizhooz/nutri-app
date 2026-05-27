import logging

from fastapi import HTTPException, status

from app.models.enums import CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.models.enums import CourseType as CT
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe import RecipeManualCreate
from app.services.search_service import RecipeSearchService
from app.core.utils import slugify

logger = logging.getLogger(__name__)

_SLUG_MAX_ATTEMPTS = 100


class RecipeService:
    def __init__(
        self, repository: RecipeRepository, search: RecipeSearchService
    ) -> None:
        self._repository = repository
        self._search = search

    async def create_manual(self, data: RecipeManualCreate, user_id: str) -> Recipe:
        recipe_ingredients: list[RecipeIngredient] = []
        for ing in data.ingredients:
            ingredient = await self._repository.get_or_create_ingredient(ing.name)
            recipe_ingredients.append(
                RecipeIngredient(
                    ingredient_id=ingredient.id,
                    quantity=ing.quantity,
                    unit=ing.unit,
                )
            )

        slug = await self._generate_unique_slug(slugify(data.title))

        recipe = Recipe(
            title=data.title,
            slug=slug,
            description=data.description,
            instructions=data.instructions,
            prep_time_minutes=data.prep_time_minutes,
            cook_time_minutes=data.cook_time_minutes,
            servings=data.servings,
            course_type=data.course_type or CT.MAIN_COURSE,
            free_tags=data.free_tags,
            difficulty=DifficultyLevel.EASY,
            cuisine_origin=CuisineOrigin.FRENCH,
            origin_recipe=RecipeOrigin.PERSONAL,
            created_by_user_id=user_id,
        )

        recipe = await self._repository.create(recipe, recipe_ingredients)

        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES indexing failed for recipe %s: %s", recipe.id, exc)

        return recipe

    async def update_image_url(
        self, recipe_id: int, user_id: str, image_url: str
    ) -> Recipe:
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        if recipe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recette introuvable.",
            )
        if recipe.created_by_user_id is None or str(recipe.created_by_user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas l'auteur de cette recette.",
            )
        recipe = await self._repository.update_image_url(recipe_id, image_url)
        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES reindex failed for recipe %s: %s", recipe_id, exc)
        return recipe

    async def _generate_unique_slug(
        self, base_slug: str, exclude_id: int | None = None
    ) -> str:
        if not await self._repository.slug_exists(base_slug, exclude_id):
            return base_slug
        for i in range(1, _SLUG_MAX_ATTEMPTS + 1):
            candidate = f"{base_slug}-{i}"
            if not await self._repository.slug_exists(candidate, exclude_id):
                return candidate
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Impossible de générer un slug unique pour ce titre.",
        )
