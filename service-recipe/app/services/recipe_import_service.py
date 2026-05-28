from dataclasses import dataclass, field

from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe_import import RecipeImportPayload
from app.services.recipe_service import RecipeService


@dataclass
class ImportReport:
    ingredients_upserted: int = 0
    recipes_created: int = 0
    recipe_slugs: list[str] = field(default_factory=list)


class RecipeImportService:
    """Bulk import of recipes (+ ingredient catalog) from a parsed JSON payload."""

    def __init__(
        self, repository: RecipeRepository, recipe_service: RecipeService
    ) -> None:
        self._repository = repository
        self._recipe_service = recipe_service

    async def import_payload(self, payload: RecipeImportPayload) -> ImportReport:
        upserted = await self._repository.upsert_ingredients(payload.ingredients)

        slugs: list[str] = []
        for item in payload.recipes:
            recipe = await self._recipe_service.create_full(
                item, payload.created_by_user_id
            )
            slugs.append(recipe.slug)

        return ImportReport(
            ingredients_upserted=upserted,
            recipes_created=len(slugs),
            recipe_slugs=slugs,
        )
