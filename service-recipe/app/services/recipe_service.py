import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import (
    ImageNotInSuggestions,
    ImageServiceUnavailable,
    RecipeForbidden,
    RecipeNotFound,
    SlugGenerationError,
)
from app.core.http_client import NutritionServiceClient
from app.models.enums import CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.models.enums import CourseType as CT
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe import (
    PaginatedRecipeResponse,
    RecipeCreate,
    RecipeManualCreate,
    RecipeUpdate,
)
from app.schemas.recipe_import import RecipeImportItem
from app.services.search_service import RecipeSearchService
from app.services.unsplash_service import ImageSuggestion, UnsplashService
from app.core.utils import normalize_keyword, slugify

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

    async def get_by_slug(self, slug: str, account_id: str) -> Recipe:
        recipe = await self._repository.get_by_slug_with_relations(slug)
        return self._ensure_account(recipe, account_id)

    async def get_by_id(self, recipe_id: int, account_id: str) -> Recipe:
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        return self._ensure_account(recipe, account_id)

    async def list_recipes(
        self,
        page: int,
        page_size: int,
        course_type: str | None = None,
        account_id: str | None = None,
    ) -> PaginatedRecipeResponse:
        items, total = await self._repository.list_paginated(
            page, page_size, course_type, account_id
        )
        pages = max(1, -(-total // page_size))  # ceiling division
        return PaginatedRecipeResponse(
            items=items, total=total, page=page, page_size=page_size, pages=pages
        )

    async def update(
        self, recipe_id: int, data: RecipeUpdate, account_id: str | None
    ) -> Recipe:
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        # account_id None = appelant de confiance (crawler/commit) : pas de
        # contrôle d'appartenance, mais la recette doit exister.
        if account_id is None:
            if recipe is None:
                raise RecipeNotFound()
        else:
            self._ensure_account(recipe, account_id)

        update_fields = data.model_dump(
            exclude_unset=True, exclude={"recipe_ingredients"}
        )
        if "title" in update_fields:
            update_fields["slug"] = await self._generate_unique_slug(
                slugify(update_fields["title"]), exclude_id=recipe_id
            )

        updated = await self._repository.apply_update(
            recipe, update_fields, data.recipe_ingredients
        )
        try:
            await self._search.index_recipe(updated)
        except Exception as exc:
            logger.warning("ES reindex failed for recipe %s: %s", recipe_id, exc)
        return updated

    async def delete(self, recipe_id: int, account_id: str) -> None:
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        recipe = self._ensure_account(recipe, account_id)
        await self._repository.delete(recipe)
        try:
            await self._search.delete_recipe(recipe_id)
        except Exception as exc:
            logger.warning("ES delete failed for recipe %s: %s", recipe_id, exc)

    async def delete_by_user(self, user_id: str) -> int:
        """Delete all recipes authored by ``user_id`` and unindex them."""
        count = await self._repository.delete_by_user(user_id)
        try:
            await self._search.delete_by_user(user_id)
        except Exception as exc:
            logger.warning("ES delete-by-user failed for %s: %s", user_id, exc)
        return count

    async def create_manual(
        self, data: RecipeManualCreate, user_id: str, account_id: str
    ) -> Recipe:
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
            account_id=account_id,
        )

        recipe = await self._repository.create(recipe, recipe_ingredients)
        recipe = await self._index_and_enrich(
            recipe, data.ingredients, user_id, account_id
        )
        return await self._attach_suggestions(recipe)

    async def create(self, data: RecipeCreate, user_id: str, account_id: str) -> Recipe:
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
            account_id=account_id,
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

    async def create_full(
        self, data: RecipeImportItem, user_id: str, account_id: str
    ) -> Recipe:
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
            account_id=account_id,
        )

        recipe = await self._repository.create(recipe, recipe_ingredients)
        recipe = await self._index_and_enrich(
            recipe, data.ingredients, user_id, account_id
        )
        # Import en masse : on NE lance PAS de recherche d'image Unsplash par
        # recette. Sinon un import de N recettes = N appels Unsplash, ce qui crame
        # le quota (50 req/h en clé "demo") et casse la recherche d'image pour
        # tout le monde pendant une heure. L'image explicite du fichier
        # (``image_url``) est conservée ; les recettes sans image en restent
        # dépourvues et l'auteur peut lancer une recherche à la demande ensuite.
        return recipe

    async def push_to_account(
        self,
        recipe_ids: list[int],
        source_account_id: str,
        target_account_id: str,
    ) -> tuple[list[Recipe], list[int]]:
        """Copie (one-shot) des recettes du compte coach vers un compte client.

        Pour chaque recette source (qui doit appartenir à ``source_account_id``),
        crée une copie indépendante dans ``target_account_id`` : macros recopiées
        (pas de ré-extraction), nouvel id/slug, ``source_recipe_id`` renseigné pour
        la traçabilité et l'anti-doublon (une source déjà poussée est ignorée).

        Retourne ``(créées, ignorées)`` où ``ignorées`` liste les ids source déjà
        présents dans le compte cible. Cf. docs/coaching_model.md §6.
        """
        created: list[Recipe] = []
        skipped: list[int] = []
        for recipe_id in recipe_ids:
            source = await self._repository.get_by_id_with_relations(recipe_id)
            # 403/404 si la recette n'est pas dans la bibliothèque du coach.
            self._ensure_account(source, source_account_id)

            if await self._repository.find_clone(target_account_id, recipe_id):
                skipped.append(recipe_id)
                continue

            slug = await self._generate_unique_slug(slugify(source.title))
            clone = Recipe(
                title=source.title,
                slug=slug,
                description=source.description,
                instructions=source.instructions,
                prep_time_minutes=source.prep_time_minutes,
                cook_time_minutes=source.cook_time_minutes,
                servings=source.servings,
                difficulty=source.difficulty,
                cuisine_origin=source.cuisine_origin,
                origin_recipe=source.origin_recipe,
                course_type=source.course_type,
                tags=source.tags,
                free_tags=source.free_tags,
                book_name=source.book_name,
                source_url=source.source_url,
                image_url=source.image_url,
                image_thumb_url=source.image_thumb_url,
                image_search_keyword=source.image_search_keyword,
                comment=source.comment,
                rating=source.rating,
                # Macros recopiées telles quelles (copie one-shot, pas de resync).
                calories_per_serving=source.calories_per_serving,
                proteins_per_serving=source.proteins_per_serving,
                carbs_per_serving=source.carbs_per_serving,
                fats_per_serving=source.fats_per_serving,
                created_by_user_id=source.created_by_user_id,
                account_id=target_account_id,
                source_recipe_id=source.id,
            )
            ingredients = [
                RecipeIngredient(
                    ingredient_id=ri.ingredient_id,
                    quantity=ri.quantity,
                    unit=ri.unit,
                )
                for ri in source.recipe_ingredients
            ]
            clone = await self._repository.create(clone, ingredients)
            try:
                await self._search.index_recipe(clone)
            except Exception as exc:
                logger.warning(
                    "ES indexing failed for pushed recipe %s: %s", clone.id, exc
                )
            created.append(clone)
        return created, skipped

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
        self, recipe: Recipe, ingredients, user_id: str, account_id: str
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
                account_id=account_id,
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
                # Ré-indexe pour que le doc ES porte les macros fraîchement calculées.
                try:
                    await self._search.index_recipe(recipe)
                except Exception as exc:
                    logger.warning(
                        "ES macro reindex failed for recipe %s: %s", recipe.id, exc
                    )

        return recipe

    async def update_image_url(
        self, recipe_id: int, account_id: str, image_url: str
    ) -> Recipe:
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        self._ensure_account(recipe, account_id)
        recipe = await self._repository.update_image_url(recipe_id, image_url)
        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES reindex failed for recipe %s: %s", recipe_id, exc)
        return recipe

    async def _attach_suggestions(self, recipe: Recipe) -> Recipe:
        """Query Unsplash with the recipe title, persist the proposals, and set
        the first result as the recipe image when none was provided.

        Best-effort: a failure (or no API key) leaves an empty suggestion set and
        never breaks recipe creation. The proposals are kept so the author can
        still switch image later via ``select_image``. An explicit ``image_url``
        (e.g. JSON import) is preserved and never overwritten.
        """
        # Création (manuelle) : best-effort. Une indisponibilité Unsplash ne doit
        # jamais casser la création — on retombe sur 0 proposition. _search_images
        # propage ImageServiceUnavailable (levée par l'appel Unsplash sous-jacent).
        try:
            suggestions = await self._search_images(recipe.title)
        except ImageServiceUnavailable:
            suggestions = []
        updated = await self._repository.update_image_suggestions(
            recipe.id, recipe.title, [s.to_dict() for s in suggestions]
        )
        recipe = updated or recipe

        # On pose arbitrairement la 1ʳᵉ proposition comme image finale, sauf si la
        # recette en a déjà une (import avec image_url explicite).
        if suggestions and not recipe.image_url:
            recipe = await self._auto_select_first(recipe, suggestions[0])
        return recipe

    async def _auto_select_first(
        self, recipe: Recipe, suggestion: ImageSuggestion
    ) -> Recipe:
        """Sélectionne d'office une proposition Unsplash comme image de la recette."""
        # Guideline Unsplash : signaler l'usage de la photo (best-effort).
        await self._unsplash.track_download(suggestion.download_location)
        selected = await self._repository.select_final_image(
            recipe.id, suggestion.full_url, suggestion.thumb_url
        )
        recipe = selected or recipe
        try:
            await self._search.index_recipe(recipe)
        except Exception as exc:
            logger.warning("ES reindex failed for recipe %s: %s", recipe.id, exc)
        return recipe

    def _ensure_account(self, recipe: Recipe | None, account_id: str) -> Recipe:
        """Contrôle d'appartenance au compte actif (frontière multicomptes).

        404 si la recette n'existe pas, 403 si elle appartient à un autre compte.
        """
        if recipe is None:
            raise RecipeNotFound()
        if recipe.account_id is None or str(recipe.account_id) != account_id:
            raise RecipeForbidden()
        return recipe

    async def refresh_suggestions(
        self, recipe_id: int, keyword: str, account_id: str
    ) -> Recipe:
        """Re-run an Unsplash search with a free keyword and store new proposals."""
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        self._ensure_account(recipe, account_id)
        suggestions = await self._search_images(keyword)
        updated = await self._repository.update_image_suggestions(
            recipe_id, keyword, [s.to_dict() for s in suggestions]
        )
        return updated or recipe

    async def _search_images(self, keyword: str) -> list[ImageSuggestion]:
        """Search Unsplash for ``keyword``, backed by a persistent cache.

        The cache (table ``image_search_cache``) is keyed by the normalized
        keyword, so several recipes sharing a title hit Unsplash only once. A fresh
        entry is reused as-is; otherwise we query Unsplash — asking for more results
        than we display, since the cost is now amortized — and store them for next
        time. Empty results are never cached so a transient failure (or a missing
        API key) doesn't poison the entry.
        """
        cache_key = normalize_keyword(keyword)
        if not cache_key:
            return []

        # Naïf (sans tzinfo) pour rester comparable aux timestamps stockés par
        # ``func.now()`` (colonne ``timestamp without time zone``).
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        fresh_after = now - timedelta(days=settings.UNSPLASH_CACHE_TTL_DAYS)
        cached = await self._repository.get_cached_image_suggestions(
            cache_key, fresh_after=fresh_after
        )
        if cached is not None:
            return [ImageSuggestion(**s) for s in cached]

        suggestions = await self._unsplash.search(
            keyword, count=settings.UNSPLASH_SUGGESTION_COUNT
        )
        if suggestions:
            await self._repository.upsert_cached_image_suggestions(
                cache_key, [s.to_dict() for s in suggestions]
            )
        return suggestions

    async def select_image(
        self, recipe_id: int, unsplash_id: str, account_id: str
    ) -> Recipe:
        """Validate a proposed image and persist it as the final recipe image."""
        recipe = await self._repository.get_by_id_with_relations(recipe_id)
        self._ensure_account(recipe, account_id)

        chosen = next(
            (
                s
                for s in (recipe.image_suggestions or [])
                if s.get("unsplash_id") == unsplash_id
            ),
            None,
        )
        if chosen is None:
            raise ImageNotInSuggestions()

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
        raise SlugGenerationError()
