from dataclasses import dataclass, field

from app.core.http_client import ServicesUserClient
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

        # Multicomptes : toutes les recettes du payload partagent le même
        # created_by_user_id → on résout son compte une seule fois et on l'attribue.
        async with ServicesUserClient() as user_client:
            account_id = await user_client.default_account(payload.created_by_user_id)
        if not account_id:
            raise ValueError(
                f"Aucun compte pour created_by_user_id={payload.created_by_user_id}"
            )

        slugs: list[str] = []
        for item in payload.recipes:
            recipe = await self._recipe_service.create_full(
                item, payload.created_by_user_id, account_id
            )
            slugs.append(recipe.slug)

        return ImportReport(
            ingredients_upserted=upserted,
            recipes_created=len(slugs),
            recipe_slugs=slugs,
        )
