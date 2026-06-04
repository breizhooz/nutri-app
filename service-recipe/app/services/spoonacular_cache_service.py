import asyncio
import logging
from dataclasses import dataclass

from app.core.exceptions import RecipeNotFound
from app.models.recipe import Recipe
from app.models.spoonacular_cache import SpoonacularRecipeCache
from app.repositories.spoonacular_cache_repository import SpoonacularCacheRepository
from app.services.recipe_service import RecipeService
from app.services.recipe_translator import RecipeTranslator
from app.services.spoonacular_mapper import spoonacular_to_import_item
from app.services.spoonacular_service import (
    DEFAULT_RECIPE_COUNT,
    SpoonacularClient,
)

logger = logging.getLogger(__name__)


@dataclass
class SpoonacularFetchReport:
    """Bilan d'un fetch quotidien : recettes reçues, créées, mises à jour."""

    fetched: int
    created: int
    updated: int


class SpoonacularCacheService:
    """Orchestration : récupère des recettes Spoonacular et les met en cache.

    La logique métier vit ici (le client ne fait que l'appel HTTP, le repository
    que l'accès BD), conformément à l'architecture du service.
    """

    def __init__(
        self,
        repository: SpoonacularCacheRepository,
        client: SpoonacularClient | None = None,
        translator: RecipeTranslator | None = None,
    ) -> None:
        self._repository = repository
        self._client = client or SpoonacularClient()
        self._translator = translator or RecipeTranslator()

    async def fetch_and_cache(
        self, count: int = DEFAULT_RECIPE_COUNT
    ) -> SpoonacularFetchReport:
        """Récupère ``count`` recettes (1..5), les traduit en FR et les met en cache."""
        recipes = await self._client.random_recipes(count)

        created = 0
        for recipe in recipes:
            # Traduction EN→FR (best-effort, hors event loop car deep-translator
            # est synchrone et fait des appels réseau).
            payload_fr = await asyncio.to_thread(
                self._translator.translate_payload, recipe.payload
            )
            title_fr = (
                payload_fr.get("title") if isinstance(payload_fr, dict) else None
            ) or recipe.title
            was_created = await self._repository.upsert(
                spoonacular_id=recipe.spoonacular_id,
                title=title_fr,
                image_url=recipe.image_url,
                source_url=recipe.source_url,
                payload=payload_fr,
            )
            created += 1 if was_created else 0

        report = SpoonacularFetchReport(
            fetched=len(recipes),
            created=created,
            updated=len(recipes) - created,
        )
        logger.info(
            "Spoonacular: %d récupérée(s), %d créée(s), %d mise(s) à jour.",
            report.fetched,
            report.created,
            report.updated,
        )
        return report

    async def get_random(self) -> SpoonacularRecipeCache:
        """Renvoie une recette du cache au hasard (pour « Shake ta recette »).

        Lève ``RecipeNotFound`` si le cache est vide (mappé en 404 localisé).
        """
        recipe = await self._repository.get_random()
        if recipe is None:
            raise RecipeNotFound()
        return recipe

    async def add_to_personal_list(
        self,
        spoonacular_id: int,
        user_id: str,
        recipe_service: RecipeService,
    ) -> Recipe:
        """Ajoute une recette du cache à la liste personnelle de ``user_id``.

        Passe par le « process habituel » (``RecipeService.create_full``) :
        hydratation/création des ingrédients, calcul des macros via
        service-nutrition, indexation Elasticsearch. Lève ``RecipeNotFound`` si la
        recette n'est pas dans le cache Spoonacular.
        """
        cached = await self._repository.get_by_spoonacular_id(spoonacular_id)
        if cached is None:
            raise RecipeNotFound()
        item = spoonacular_to_import_item(cached.payload or {})
        return await recipe_service.create_full(item, user_id)
