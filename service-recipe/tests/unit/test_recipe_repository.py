from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.recipe_repository import RecipeRepository


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _make_scalar_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ─── slug_exists ──────────────────────────────────────────────────────────────


class TestSlugExists:
    @pytest.fixture
    def session(self):
        return _make_session()

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_returns_true_when_slug_found(self, repo, session):
        session.execute.return_value = _make_scalar_result(42)
        result = await repo.slug_exists("my-slug")
        assert result is True

    async def test_returns_false_when_slug_not_found(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        result = await repo.slug_exists("my-slug")
        assert result is False

    async def test_exclude_id_does_not_prevent_query(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        result = await repo.slug_exists("my-slug", exclude_id=1)
        assert result is False
        session.execute.assert_called_once()


# ─── get_or_create_ingredient ─────────────────────────────────────────────────


class TestGetOrCreateIngredient:
    @pytest.fixture
    def session(self):
        return _make_session()

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_returns_existing_ingredient(self, repo, session):
        existing = MagicMock()
        existing.id = 7
        existing.name = "farine"
        session.execute.return_value = _make_scalar_result(existing)

        result = await repo.get_or_create_ingredient("farine")

        assert result.id == 7
        session.add.assert_not_called()

    async def test_creates_ingredient_when_not_found(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        session.flush = AsyncMock()

        result = await repo.get_or_create_ingredient("quinoa")

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result.name == "quinoa"

    async def test_new_ingredient_has_correct_name(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        session.flush = AsyncMock()

        ingredient = await repo.get_or_create_ingredient("huile d'olive")
        assert ingredient.name == "huile d'olive"


# ─── create ───────────────────────────────────────────────────────────────────


class TestCreate:
    @pytest.fixture
    def session(self):
        session = _make_session()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_adds_recipe_and_flushes(self, repo, session):
        recipe = MagicMock()
        recipe.id = 1

        async def fake_reload(rid):
            return recipe

        repo.get_by_id_with_relations = fake_reload

        await repo.create(recipe, [])

        session.add.assert_called_with(recipe)
        session.flush.assert_called()

    async def test_assigns_recipe_id_to_each_ingredient(self, repo, session):
        recipe = MagicMock()
        recipe.id = 5

        ri1 = MagicMock()
        ri1.recipe_id = None
        ri2 = MagicMock()
        ri2.recipe_id = None

        async def fake_reload(rid):
            return recipe

        repo.get_by_id_with_relations = fake_reload

        await repo.create(recipe, [ri1, ri2])

        assert ri1.recipe_id == 5
        assert ri2.recipe_id == 5
        assert session.add.call_count == 3  # recipe + 2 ingredients

    async def test_commits_after_adding(self, repo, session):
        recipe = MagicMock()
        recipe.id = 1

        async def fake_reload(rid):
            return recipe

        repo.get_by_id_with_relations = fake_reload

        await repo.create(recipe, [])
        session.commit.assert_called_once()
