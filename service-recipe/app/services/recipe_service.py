import logging

from fastapi import HTTPException, status

from app.core.http_client import NutritionServiceClient
from app.models.enums import CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.models.enums import CourseType as CT
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe import RecipeManualCreate
from app.schemas.recipe_import import RecipeImportItem
from app.services.search_service import RecipeSearchService
from app.core.utils import slugify

logger = logging.getLogger(__name__)

_SLUG_MAX_ATTEMPTS = 100


class RecipeService:
    def __init__(
        self,
        repository: RecipeRepository,
        search: RecipeSearchService,
        nutrition_client: NutritionServiceClient | None = None,
    ) -> None:
        self._repository = repository
        self._search = search
        self._nutrition = nutrition_client or NutritionServiceClient()

    async def create_manual(self, data: RecipeManualCreate, user_id: str) -> Recipe:
        recipe_ingredients = await self._resolve_ingredients(data.ingredients)
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
        return await self._index_and_enrich(recipe, data.ingredients, user_id)

    async def create_full(self, data: RecipeImportItem, user_id: str) -> Recipe:
        """Create a recipe honoring every field (used by the JSON import)."""
        recipe_ingredients = await self._resolve_ingredients(data.ingredients)
        slug = await self._generate_unique_slug(slugify(data.title))

        recipe = Recipe(
            title=data.title,
            slug=slug,
            description=data.description,
            instructions=data.instructions,
            prep_time_minutes=data.prep_time_minutes,
            cook_time_minutes=data.cook_time_minutes,
            servings=data.servings,
            difficulty=data.difficulty,
            cuisine_origin=data.cuisine_origin,
            origin_recipe=data.origin_recipe,
            course_type=data.course_type,
            tags=data.tags,
            free_tags=data.free_tags,
            book_name=data.book_name,
            source_url=data.source_url,
            image_url=data.image_url,
            created_by_user_id=user_id,
        )

        recipe = await self._repository.create(recipe, recipe_ingredients)
        return await self._index_and_enrich(recipe, data.ingredients, user_id)

    async def _resolve_ingredients(self, ingredients) -> list[RecipeIngredient]:
        rows: list[RecipeIngredient] = []
        for ing in ingredients:
            ingredient = await self._repository.get_or_create_ingredient(ing.name)
            rows.append(
                RecipeIngredient(
                    ingredient_id=ingredient.id,
                    quantity=ing.quantity,
                    unit=ing.unit,
                )
            )
        return rows

    async def _index_and_enrich(
        self, recipe: Recipe, ingredients, user_id: str
    ) -> Recipe:
        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES indexing failed for recipe %s: %s", recipe.id, exc)

        if ingredients:
            nutrition = await self._nutrition.calculate(
                recipe_slug=recipe.slug,
                servings=recipe.servings,
                user_id=user_id,
                ingredients=[
                    {"name": i.name, "quantity": i.quantity, "unit": i.unit}
                    for i in ingredients
                ],
            )
            if nutrition is not None:
                await self._repository.update_macros(
                    recipe.id,
                    calories=nutrition.calories_per_serving,
                    proteins=nutrition.proteins_per_serving,
                    carbs=nutrition.carbs_per_serving,
                    fats=nutrition.fats_per_serving,
                )
                recipe = (
                    await self._repository.get_by_id_with_relations(recipe.id) or recipe
                )

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
        if (
            recipe.created_by_user_id is None
            or str(recipe.created_by_user_id) != user_id
        ):
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
