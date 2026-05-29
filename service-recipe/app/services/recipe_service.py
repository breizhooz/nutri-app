import logging

from fastapi import HTTPException, status

from app.core.http_client import NutritionServiceClient
from app.models.enums import CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.models.enums import CourseType as CT
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe import RecipeCreate, RecipeManualCreate
from app.schemas.recipe_import import RecipeImportItem
from app.services.search_service import RecipeSearchService
from app.services.unsplash_service import UnsplashService
from app.core.utils import slugify

logger = logging.getLogger(__name__)

_SLUG_MAX_ATTEMPTS = 100


class RecipeService:
    def __init__(
        self,
        repository: RecipeRepository,
        search: RecipeSearchService,
        nutrition_client: NutritionServiceClient | None = None,
        unsplash: UnsplashService | None = None,
    ) -> None:
        self._repository = repository
        self._search = search
        self._nutrition = nutrition_client or NutritionServiceClient()
        self._unsplash = unsplash or UnsplashService()

    async def counts_by_user(self) -> dict[str, int]:
        """Return a mapping {user_id: number_of_recipes} for all authors."""
        return {
            user_id: count for user_id, count in await self._repository.count_by_user()
        }

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
        recipe = await self._index_and_enrich(recipe, data.ingredients, user_id)
        return await self._attach_suggestions(recipe)

    async def create(self, data: RecipeCreate, user_id: str) -> Recipe:
        """Generic creation path (manual UI form, crawler import via POST /recipe)."""
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
            created_by_user_id=data.created_by_user_id or user_id,
        )
        recipe_ingredients = [
            RecipeIngredient(
                ingredient_id=ing.ingredient_id,
                quantity=ing.quantity,
                unit=ing.unit,
            )
            for ing in data.recipe_ingredients
        ]
        recipe = await self._repository.create(recipe, recipe_ingredients)
        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES indexing failed for recipe %s: %s", recipe.id, exc)
        return await self._attach_suggestions(recipe)

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
        recipe = await self._index_and_enrich(recipe, data.ingredients, user_id)
        return await self._attach_suggestions(recipe)

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

    async def _attach_suggestions(self, recipe: Recipe) -> Recipe:
        """Query Unsplash with the recipe title and persist the proposals.

        Best-effort: a failure (or no API key) leaves an empty suggestion set and
        never breaks recipe creation.
        """
        suggestions = await self._unsplash.search(recipe.title)
        updated = await self._repository.update_image_suggestions(
            recipe.id, recipe.title, [s.to_dict() for s in suggestions]
        )
        return updated or recipe

    def _ensure_author(self, recipe: Recipe | None, user_id: str) -> Recipe:
        if recipe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recette introuvable."
            )
        if recipe.created_by_user_id is None or str(recipe.created_by_user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas l'auteur de cette recette.",
            )
        return recipe

    async def refresh_suggestions(
        self, recipe_id: int, keyword: str, user_id: str
    ) -> Recipe:
        """Re-run an Unsplash search with a free keyword and store new proposals."""
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        self._ensure_author(recipe, user_id)
        suggestions = await self._unsplash.search(keyword)
        updated = await self._repository.update_image_suggestions(
            recipe_id, keyword, [s.to_dict() for s in suggestions]
        )
        return updated or recipe

    async def select_image(
        self, recipe_id: int, unsplash_id: str, user_id: str
    ) -> Recipe:
        """Validate a proposed image and persist it as the final recipe image."""
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        self._ensure_author(recipe, user_id)

        chosen = next(
            (
                s
                for s in (recipe.image_suggestions or [])
                if s.get("unsplash_id") == unsplash_id
            ),
            None,
        )
        if chosen is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette image ne fait pas partie des propositions de la recette.",
            )

        # Unsplash API guideline: notify the download endpoint when a photo is used.
        await self._unsplash.track_download(chosen.get("download_location", ""))

        updated = await self._repository.select_final_image(
            recipe_id, chosen.get("full_url", ""), chosen.get("thumb_url")
        )
        recipe = updated or recipe
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
