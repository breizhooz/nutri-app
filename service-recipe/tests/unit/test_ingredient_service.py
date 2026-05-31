from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import IngredientAlreadyExists, IngredientNotFound
from app.schemas.ingredient import IngredientCreate, IngredientUpdate
from app.services.ingredient_service import IngredientService


def _make_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_name.return_value = None
    repo.get_by_id.return_value = MagicMock()
    repo.create.side_effect = lambda ingredient: ingredient
    repo.update.side_effect = lambda ingredient, fields: ingredient
    return repo


@pytest.fixture
def repo():
    return _make_repo()


@pytest.fixture
def service(repo):
    return IngredientService(repo)


class TestIngredientServiceCreate:
    async def test_creates_when_name_free(self, service, repo):
        await service.create(IngredientCreate(name="Banane"))
        repo.create.assert_called_once()
        assert repo.create.call_args[0][0].name == "Banane"

    async def test_conflict_when_name_exists(self, service, repo):
        repo.get_by_name.return_value = MagicMock()
        with pytest.raises(IngredientAlreadyExists):
            await service.create(IngredientCreate(name="Banane"))
        repo.create.assert_not_called()


class TestIngredientServiceGet:
    async def test_returns_ingredient(self, service, repo):
        ingredient = MagicMock()
        repo.get_by_id.return_value = ingredient
        assert await service.get(1) is ingredient

    async def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(IngredientNotFound):
            await service.get(1)


class TestIngredientServiceUpdate:
    async def test_only_sets_provided_fields(self, service, repo):
        ingredient = MagicMock()
        repo.get_by_id.return_value = ingredient
        await service.update(1, IngredientUpdate(calories_per_100g=89.0))
        _, fields = repo.update.call_args[0]
        assert fields == {"calories_per_100g": 89.0}

    async def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(IngredientNotFound):
            await service.update(1, IngredientUpdate(name="X"))


class TestIngredientServiceDelete:
    async def test_deletes_existing(self, service, repo):
        ingredient = MagicMock()
        repo.get_by_id.return_value = ingredient
        await service.delete(1)
        repo.delete.assert_called_once_with(ingredient)

    async def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(IngredientNotFound):
            await service.delete(1)
        repo.delete.assert_not_called()


class TestIngredientServiceList:
    async def test_delegates_to_repo(self, service, repo):
        repo.list.return_value = ["a", "b"]
        result = await service.list(skip=5, limit=10)
        assert result == ["a", "b"]
        repo.list.assert_called_once_with(5, 10)
