from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.recipe_repository import RecipeRepository
from app.schemas.recipe_import import IngredientImport


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


# ─── upsert_ingredients ───────────────────────────────────────────────────────


class TestUpsertIngredients:
    @pytest.fixture
    def session(self):
        session = _make_session()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_creates_when_absent(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        count = await repo.upsert_ingredients(
            [IngredientImport(name="quinoa", calories_per_100g=120.0)]
        )
        session.add.assert_called_once()
        session.commit.assert_called_once()
        assert count == 1

    async def test_updates_macros_when_present(self, repo, session):
        existing = MagicMock()
        existing.name = "riz"
        session.execute.return_value = _make_scalar_result(existing)
        await repo.upsert_ingredients(
            [
                IngredientImport(
                    name="riz", calories_per_100g=356.0, proteins_per_100g=6.7
                )
            ]
        )
        assert existing.calories_per_100g == 356.0
        assert existing.proteins_per_100g == 6.7
        session.add.assert_not_called()
        session.commit.assert_called_once()

    async def test_returns_total_count(self, repo, session):
        session.execute.return_value = _make_scalar_result(None)
        count = await repo.upsert_ingredients(
            [IngredientImport(name="a"), IngredientImport(name="b")]
        )
        assert count == 2
        assert session.add.call_count == 2


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


# ─── delete_by_user ───────────────────────────────────────────────────────────


def _make_rowcount_result(rowcount: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = rowcount
    return result


class TestDeleteByUser:
    @pytest.fixture
    def session(self):
        return _make_session()

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_returns_rowcount_and_commits(self, repo, session):
        session.execute.return_value = _make_rowcount_result(3)
        deleted = await repo.delete_by_user("user-1")
        assert deleted == 3
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_handles_none_rowcount(self, repo, session):
        session.execute.return_value = _make_rowcount_result(None)
        assert await repo.delete_by_user("user-1") == 0


# ─── image search cache ───────────────────────────────────────────────────────


class TestImageCache:
    @pytest.fixture
    def session(self):
        session = _make_session()
        session.commit = AsyncMock()
        session.scalar = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, session):
        return RecipeRepository(session)

    async def test_get_returns_none_on_miss(self, repo, session):
        session.scalar.return_value = None
        assert await repo.get_cached_image_suggestions("tarte") is None

    async def test_get_returns_suggestions_on_hit(self, repo, session):
        # La requête sélectionne la colonne JSON : scalar() renvoie la liste telle quelle.
        session.scalar.return_value = [{"unsplash_id": "a"}]
        out = await repo.get_cached_image_suggestions("tarte")
        assert out == [{"unsplash_id": "a"}]

    async def test_get_accepts_fresh_after(self, repo, session):
        session.scalar.return_value = [{"unsplash_id": "a"}]
        out = await repo.get_cached_image_suggestions(
            "tarte", fresh_after=datetime(2026, 1, 1)
        )
        assert out == [{"unsplash_id": "a"}]
        session.scalar.assert_awaited_once()

    async def test_upsert_inserts_when_absent(self, repo, session):
        session.scalar.return_value = None
        await repo.upsert_cached_image_suggestions("tarte", [{"unsplash_id": "a"}])
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    async def test_upsert_updates_when_present(self, repo, session):
        row = MagicMock()
        session.scalar.return_value = row
        await repo.upsert_cached_image_suggestions("tarte", [{"unsplash_id": "b"}])
        assert row.suggestions == [{"unsplash_id": "b"}]
        session.add.assert_not_called()
        session.commit.assert_awaited_once()
