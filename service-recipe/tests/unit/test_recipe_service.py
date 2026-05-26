from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.enums import CourseType, CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.schemas.recipe import ManualIngredient, RecipeManualCreate
from app.services.recipe_service import RecipeService


# ─── Factories ────────────────────────────────────────────────────────────────


def _make_repo(slug_exists: bool = False) -> AsyncMock:
    repo = AsyncMock()
    repo.slug_exists.return_value = slug_exists
    repo.get_or_create_ingredient.side_effect = lambda name: _make_ingredient(name)
    recipe = _make_recipe()
    repo.create.return_value = recipe
    return repo


def _make_ingredient(name: str) -> MagicMock:
    ing = MagicMock()
    ing.id = abs(hash(name)) % 1000 + 1
    ing.name = name
    return ing


def _make_recipe(recipe_id: int = 1, title: str = "Tarte aux pommes") -> MagicMock:
    r = MagicMock()
    r.id = recipe_id
    r.title = title
    r.recipe_ingredients = []
    return r


def _make_search() -> AsyncMock:
    search = AsyncMock()
    search.index_recipe.return_value = None
    return search


def _make_data(**kwargs) -> RecipeManualCreate:
    defaults = dict(
        title="Tarte aux pommes",
        description=None,
        instructions="Mélanger et cuire.",
        servings=4,
        prep_time_minutes=None,
        cook_time_minutes=None,
        course_type=None,
        free_tags=[],
        ingredients=[],
    )
    defaults.update(kwargs)
    return RecipeManualCreate(**defaults)


# ─── create_manual ────────────────────────────────────────────────────────────


class TestRecipeServiceCreateManual:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def service(self, repo, search):
        return RecipeService(repo, search)

    async def test_returns_created_recipe(self, service, repo):
        result = await service.create_manual(_make_data(), user_id="user-1")
        assert result is repo.create.return_value

    async def test_calls_repository_create(self, service, repo):
        await service.create_manual(_make_data(), user_id="user-1")
        repo.create.assert_called_once()

    async def test_sets_user_id_on_recipe(self, service, repo):
        await service.create_manual(_make_data(), user_id="user-42")
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.created_by_user_id == "user-42"

    async def test_defaults_course_type_to_main_course(self, service, repo):
        await service.create_manual(_make_data(course_type=None), user_id="u")
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.course_type == CourseType.MAIN_COURSE

    async def test_explicit_course_type_preserved(self, service, repo):
        await service.create_manual(
            _make_data(course_type=CourseType.DESSERT), user_id="u"
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.course_type == CourseType.DESSERT

    async def test_sets_defaults_for_enums(self, service, repo):
        await service.create_manual(_make_data(), user_id="u")
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.difficulty == DifficultyLevel.EASY
        assert recipe_arg.cuisine_origin == CuisineOrigin.FRENCH
        assert recipe_arg.origin_recipe == RecipeOrigin.PERSONAL

    async def test_resolves_ingredients(self, service, repo):
        data = _make_data(
            ingredients=[
                ManualIngredient(name="farine", quantity=200.0, unit="g"),
                ManualIngredient(name="oeufs", quantity=3.0, unit="unité"),
            ]
        )
        await service.create_manual(data, user_id="u")
        assert repo.get_or_create_ingredient.call_count == 2
        calls = [c[0][0] for c in repo.get_or_create_ingredient.call_args_list]
        assert "farine" in calls
        assert "oeufs" in calls

    async def test_passes_ingredient_rows_to_create(self, service, repo):
        data = _make_data(
            ingredients=[ManualIngredient(name="sel", quantity=1.0, unit="g")]
        )
        await service.create_manual(data, user_id="u")
        _, recipe_ingredients = repo.create.call_args[0]
        assert len(recipe_ingredients) == 1
        assert recipe_ingredients[0].unit == "g"
        assert recipe_ingredients[0].quantity == 1.0

    async def test_indexes_recipe_in_search(self, service, repo, search):
        recipe = _make_recipe()
        repo.create.return_value = recipe
        await service.create_manual(_make_data(), user_id="u")
        search.index_recipe.assert_called_once_with(recipe)

    async def test_es_failure_does_not_raise(self, service, repo, search):
        search.index_recipe.side_effect = Exception("ES down")
        result = await service.create_manual(_make_data(), user_id="u")
        assert result is not None


# ─── _generate_unique_slug ────────────────────────────────────────────────────


class TestGenerateUniqueSlug:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def service(self, repo, search):
        return RecipeService(repo, search)

    async def test_returns_base_slug_when_free(self, service, repo):
        repo.slug_exists.return_value = False
        slug = await service._generate_unique_slug("tarte-aux-pommes")
        assert slug == "tarte-aux-pommes"

    async def test_appends_counter_on_first_conflict(self, service, repo):
        repo.slug_exists.side_effect = [True, False]
        slug = await service._generate_unique_slug("tarte-aux-pommes")
        assert slug == "tarte-aux-pommes-1"

    async def test_increments_counter_until_free(self, service, repo):
        repo.slug_exists.side_effect = [True, True, True, False]
        slug = await service._generate_unique_slug("tarte-aux-pommes")
        assert slug == "tarte-aux-pommes-3"

    async def test_raises_422_after_max_attempts(self, service, repo):
        repo.slug_exists.return_value = True
        with pytest.raises(HTTPException) as exc:
            await service._generate_unique_slug("tarte-aux-pommes")
        assert exc.value.status_code == 422
