from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.recipe_import import (
    IngredientImport,
    RecipeImportItem,
    RecipeImportPayload,
)
from app.services.recipe_import_service import RecipeImportService


@pytest.fixture(autouse=True)
def _mock_user_client():
    """Multicomptes : l'import résout account_id via service-user. On le stub."""
    client = AsyncMock()
    client.default_account = AsyncMock(return_value="acc-1")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "app.services.recipe_import_service.ServicesUserClient", return_value=cm
    ):
        yield


def _make_repo(upserted: int = 0) -> AsyncMock:
    repo = AsyncMock()
    repo.upsert_ingredients.return_value = upserted
    return repo


def _make_recipe_service() -> AsyncMock:
    service = AsyncMock()

    def _create_full(item, user_id, account_id):
        recipe = MagicMock()
        recipe.slug = item.title.lower().replace(" ", "-")
        return recipe

    service.create_full.side_effect = _create_full
    return service


def _payload(**kwargs) -> RecipeImportPayload:
    defaults = dict(
        created_by_user_id="user-1",
        ingredients=[IngredientImport(name="riz", calories_per_100g=356.0)],
        recipes=[RecipeImportItem(title="Risotto", instructions="x")],
    )
    defaults.update(kwargs)
    return RecipeImportPayload(**defaults)


class TestImportPayload:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def recipe_service(self):
        return _make_recipe_service()

    @pytest.fixture
    def service(self, repo, recipe_service):
        return RecipeImportService(repo, recipe_service)

    async def test_upserts_ingredients(self, service, repo):
        await service.import_payload(_payload())
        repo.upsert_ingredients.assert_called_once()

    async def test_creates_each_recipe(self, service, recipe_service):
        payload = _payload(
            recipes=[
                RecipeImportItem(title="A", instructions="x"),
                RecipeImportItem(title="B", instructions="x"),
            ]
        )
        await service.import_payload(payload)
        assert recipe_service.create_full.call_count == 2

    async def test_forwards_user_id(self, service, recipe_service):
        await service.import_payload(_payload(created_by_user_id="user-42"))
        _, user_id, account_id = recipe_service.create_full.call_args[0]
        assert user_id == "user-42"
        assert account_id == "acc-1"

    async def test_report_aggregates_counts(self, repo, recipe_service):
        repo.upsert_ingredients.return_value = 3
        service = RecipeImportService(repo, recipe_service)
        payload = _payload(recipes=[RecipeImportItem(title="A", instructions="x")])
        report = await service.import_payload(payload)
        assert report.ingredients_upserted == 3
        assert report.recipes_created == 1
        assert report.recipe_slugs == ["a"]

    async def test_no_recipes_still_upserts(self, service, repo, recipe_service):
        await service.import_payload(_payload(recipes=[]))
        repo.upsert_ingredients.assert_called_once()
        recipe_service.create_full.assert_not_called()
