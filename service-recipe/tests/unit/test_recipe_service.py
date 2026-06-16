from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import RecipeForbidden, RecipeNotFound, SlugGenerationError
from app.core.http_client import NutritionResult
from app.models.enums import CourseType, CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.schemas.recipe import ManualIngredient, RecipeManualCreate, RecipeUpdate
from app.schemas.recipe_import import RecipeImportItem, RecipeIngredientImport
from app.services.recipe_service import RecipeService


# ─── Factories ────────────────────────────────────────────────────────────────


def _make_nutrition_client(result: NutritionResult | None = None) -> AsyncMock:
    client = AsyncMock()
    client.calculate.return_value = result
    return client


def _make_repo(slug_exists: bool = False) -> AsyncMock:
    repo = AsyncMock()
    repo.slug_exists.return_value = slug_exists
    repo.get_or_create_ingredient.side_effect = lambda name: _make_ingredient(name)
    recipe = _make_recipe()
    repo.create.return_value = recipe
    repo.get_by_id_with_relations.return_value = recipe
    repo.update_image_suggestions.return_value = recipe
    repo.select_final_image.return_value = recipe
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


def _make_import_item(**kwargs) -> RecipeImportItem:
    defaults = dict(
        title="Risotto aux champignons",
        instructions="Cuire le riz.",
        servings=4,
        ingredients=[],
    )
    defaults.update(kwargs)
    return RecipeImportItem(**defaults)


# ─── create_manual ────────────────────────────────────────────────────────────


class TestRecipeServiceCreateManual:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def nutrition(self):
        return _make_nutrition_client()

    @pytest.fixture
    def service(self, repo, search, nutrition):
        return RecipeService(repo, search, nutrition_client=nutrition)

    async def test_returns_created_recipe(self, service, repo):
        result = await service.create_manual(
            _make_data(), user_id="user-1", account_id="acc-user-1"
        )
        assert result is repo.create.return_value

    async def test_calls_repository_create(self, service, repo):
        await service.create_manual(
            _make_data(), user_id="user-1", account_id="acc-user-1"
        )
        repo.create.assert_called_once()

    async def test_sets_user_id_on_recipe(self, service, repo):
        await service.create_manual(
            _make_data(), user_id="user-42", account_id="acc-user-42"
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.created_by_user_id == "user-42"

    async def test_defaults_course_type_to_main_course(self, service, repo):
        await service.create_manual(
            _make_data(course_type=None), user_id="u", account_id="acc-u"
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.course_type == CourseType.MAIN_COURSE

    async def test_explicit_course_type_preserved(self, service, repo):
        await service.create_manual(
            _make_data(course_type=CourseType.DESSERT), user_id="u", account_id="acc-u"
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.course_type == CourseType.DESSERT

    async def test_sets_defaults_for_enums(self, service, repo):
        await service.create_manual(_make_data(), user_id="u", account_id="acc-u")
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
        await service.create_manual(data, user_id="u", account_id="acc-u")
        assert repo.get_or_create_ingredient.call_count == 2
        calls = [c[0][0] for c in repo.get_or_create_ingredient.call_args_list]
        assert "farine" in calls
        assert "oeufs" in calls

    async def test_passes_ingredient_rows_to_create(self, service, repo):
        data = _make_data(
            ingredients=[ManualIngredient(name="sel", quantity=1.0, unit="g")]
        )
        await service.create_manual(data, user_id="u", account_id="acc-u")
        _, recipe_ingredients = repo.create.call_args[0]
        assert len(recipe_ingredients) == 1
        assert recipe_ingredients[0].unit == "g"
        assert recipe_ingredients[0].quantity == 1.0

    async def test_indexes_recipe_in_search(self, service, repo, search):
        recipe = _make_recipe()
        repo.create.return_value = recipe
        await service.create_manual(_make_data(), user_id="u", account_id="acc-u")
        search.index_recipe.assert_called_once_with(recipe)

    async def test_es_failure_does_not_raise(self, service, repo, search):
        search.index_recipe.side_effect = Exception("ES down")
        result = await service.create_manual(
            _make_data(), user_id="u", account_id="acc-u"
        )
        assert result is not None

    async def test_nutrition_called_when_ingredients_present(
        self, repo, search, nutrition
    ):
        service = RecipeService(repo, search, nutrition_client=nutrition)
        data = _make_data(
            ingredients=[ManualIngredient(name="farine", quantity=200.0, unit="g")]
        )
        await service.create_manual(data, user_id="u", account_id="acc-u")
        nutrition.calculate.assert_called_once()

    async def test_macros_saved_when_nutrition_returns_result(self, repo, search):
        result = NutritionResult(
            calories_per_serving=350.0,
            proteins_per_serving=10.0,
            carbs_per_serving=50.0,
            fats_per_serving=8.0,
        )
        nutrition = _make_nutrition_client(result=result)
        service = RecipeService(repo, search, nutrition_client=nutrition)
        data = _make_data(
            ingredients=[ManualIngredient(name="farine", quantity=200.0, unit="g")]
        )
        await service.create_manual(data, user_id="u", account_id="acc-u")
        repo.update_macros.assert_called_once_with(
            repo.create.return_value.id,
            calories=350.0,
            proteins=10.0,
            carbs=50.0,
            fats=8.0,
        )

    async def test_macros_not_saved_when_nutrition_returns_none(self, repo, search):
        nutrition = _make_nutrition_client(result=None)
        service = RecipeService(repo, search, nutrition_client=nutrition)
        data = _make_data(
            ingredients=[ManualIngredient(name="farine", quantity=200.0, unit="g")]
        )
        await service.create_manual(data, user_id="u", account_id="acc-u")
        repo.update_macros.assert_not_called()

    async def test_nutrition_not_called_when_no_ingredients(self, service, nutrition):
        await service.create_manual(
            _make_data(ingredients=[]), user_id="u", account_id="acc-u"
        )
        nutrition.calculate.assert_not_called()

    async def test_nutrition_failure_does_not_raise(self, repo, search):
        nutrition = _make_nutrition_client()
        nutrition.calculate.side_effect = Exception("timeout")
        service = RecipeService(repo, search, nutrition_client=nutrition)
        data = _make_data(
            ingredients=[ManualIngredient(name="farine", quantity=200.0, unit="g")]
        )
        with pytest.raises(Exception):
            await service.create_manual(data, user_id="u", account_id="acc-u")


# ─── create_full ──────────────────────────────────────────────────────────────


class TestRecipeServiceCreateFull:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def nutrition(self):
        return _make_nutrition_client()

    @pytest.fixture
    def service(self, repo, search, nutrition):
        return RecipeService(repo, search, nutrition_client=nutrition)

    async def test_honors_all_enum_fields(self, service, repo):
        await service.create_full(
            _make_import_item(
                difficulty=DifficultyLevel.HARD,
                cuisine_origin=CuisineOrigin.ITALIAN,
                origin_recipe=RecipeOrigin.BOOK,
                course_type=CourseType.DESSERT,
                book_name="Larousse",
            ),
            user_id="u",
            account_id="acc-u",
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.difficulty == DifficultyLevel.HARD
        assert recipe_arg.cuisine_origin == CuisineOrigin.ITALIAN
        assert recipe_arg.origin_recipe == RecipeOrigin.BOOK
        assert recipe_arg.course_type == CourseType.DESSERT
        assert recipe_arg.book_name == "Larousse"

    async def test_sets_image_url_and_tags(self, service, repo):
        await service.create_full(
            _make_import_item(image_url="http://img", free_tags=["bio"]),
            user_id="u",
            account_id="acc-u",
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.image_url == "http://img"
        assert recipe_arg.free_tags == ["bio"]

    async def test_sets_user_id(self, service, repo):
        await service.create_full(
            _make_import_item(), user_id="user-42", account_id="acc-user-42"
        )
        recipe_arg = repo.create.call_args[0][0]
        assert recipe_arg.created_by_user_id == "user-42"

    async def test_resolves_ingredients(self, service, repo):
        item = _make_import_item(
            ingredients=[
                RecipeIngredientImport(name="riz", quantity=300.0, unit="g"),
                RecipeIngredientImport(name="parmesan", quantity=60.0, unit="g"),
            ]
        )
        await service.create_full(item, user_id="u", account_id="acc-u")
        assert repo.get_or_create_ingredient.call_count == 2

    async def test_indexes_recipe_in_search(self, service, repo, search):
        recipe = _make_recipe()
        repo.create.return_value = recipe
        await service.create_full(_make_import_item(), user_id="u", account_id="acc-u")
        search.index_recipe.assert_called_once_with(recipe)

    async def test_does_not_call_unsplash_on_bulk_import(self, repo, search, nutrition):
        # L'import en masse ne doit JAMAIS interroger Unsplash (sinon N appels →
        # quota demo 50/h cramé). La recherche d'image reste à la demande.
        unsplash = AsyncMock()
        service = RecipeService(
            repo, search, nutrition_client=nutrition, unsplash=unsplash
        )
        await service.create_full(
            _make_import_item(image_url="http://img"), user_id="u", account_id="acc-u"
        )
        unsplash.search.assert_not_called()

    async def test_nutrition_called_when_ingredients_present(
        self, repo, search, nutrition
    ):
        service = RecipeService(repo, search, nutrition_client=nutrition)
        item = _make_import_item(
            ingredients=[RecipeIngredientImport(name="riz", quantity=300.0, unit="g")]
        )
        await service.create_full(item, user_id="u", account_id="acc-u")
        nutrition.calculate.assert_called_once()

    async def test_macros_saved_when_nutrition_returns_result(self, repo, search):
        result = NutritionResult(
            calories_per_serving=480.0,
            proteins_per_serving=12.0,
            carbs_per_serving=65.0,
            fats_per_serving=14.0,
        )
        nutrition = _make_nutrition_client(result=result)
        service = RecipeService(repo, search, nutrition_client=nutrition)
        item = _make_import_item(
            ingredients=[RecipeIngredientImport(name="riz", quantity=300.0, unit="g")]
        )
        await service.create_full(item, user_id="u", account_id="acc-u")
        repo.update_macros.assert_called_once_with(
            repo.create.return_value.id,
            calories=480.0,
            proteins=12.0,
            carbs=65.0,
            fats=14.0,
        )

    async def test_nutrition_not_called_when_no_ingredients(self, service, nutrition):
        await service.create_full(
            _make_import_item(ingredients=[]), user_id="u", account_id="acc-u"
        )
        nutrition.calculate.assert_not_called()


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
        return RecipeService(repo, search, nutrition_client=_make_nutrition_client())

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

    async def test_raises_after_max_attempts(self, service, repo):
        repo.slug_exists.return_value = True
        with pytest.raises(SlugGenerationError):
            await service._generate_unique_slug("tarte-aux-pommes")


# ─── read / list ──────────────────────────────────────────────────────────────


def _owned_recipe(user_id: str = "user-1") -> MagicMock:
    recipe = _make_recipe()
    recipe.created_by_user_id = user_id
    # Multicomptes : l'appartenance est désormais contrôlée par account_id.
    # On aligne account_id sur la valeur fournie (qui joue le rôle de compte).
    recipe.account_id = user_id
    return recipe


class TestRecipeServiceRead:
    @pytest.fixture
    def repo(self):
        return _make_repo()

    @pytest.fixture
    def service(self, repo):
        return RecipeService(
            repo, _make_search(), nutrition_client=_make_nutrition_client()
        )

    async def test_get_by_slug_returns_recipe(self, service, repo):
        recipe = _owned_recipe("acc-1")
        repo.get_by_slug_with_relations.return_value = recipe
        assert await service.get_by_slug("tarte", "acc-1") is recipe

    async def test_get_by_slug_raises_when_missing(self, service, repo):
        repo.get_by_slug_with_relations.return_value = None
        with pytest.raises(RecipeNotFound):
            await service.get_by_slug("inconnu", "acc-1")

    async def test_get_by_id_returns_recipe(self, service, repo):
        recipe = _owned_recipe("acc-1")
        repo.get_by_id_with_relations.return_value = recipe
        assert await service.get_by_id(1, "acc-1") is recipe

    async def test_get_by_id_raises_when_missing(self, service, repo):
        repo.get_by_id_with_relations.return_value = None
        with pytest.raises(RecipeNotFound):
            await service.get_by_id(999, "acc-1")

    async def test_get_by_slug_foreign_account_forbidden(self, service, repo):
        repo.get_by_slug_with_relations.return_value = _owned_recipe("autre-compte")
        with pytest.raises(RecipeForbidden):
            await service.get_by_slug("tarte", "acc-1")

    async def test_list_recipes_computes_pages(self, service, repo):
        repo.list_paginated.return_value = ([], 45)
        result = await service.list_recipes(page=1, page_size=20)
        assert result.total == 45
        assert result.pages == 3
        repo.list_paginated.assert_called_once_with(1, 20, None, None)

    async def test_list_recipes_empty_has_one_page(self, service, repo):
        repo.list_paginated.return_value = ([], 0)
        result = await service.list_recipes(page=1, page_size=20, course_type="dessert")
        assert result.pages == 1
        repo.list_paginated.assert_called_once_with(1, 20, "dessert", None)

    async def test_list_recipes_passes_account_filter(self, service, repo):
        repo.list_paginated.return_value = ([], 0)
        await service.list_recipes(page=1, page_size=20, account_id="acc-1")
        repo.list_paginated.assert_called_once_with(1, 20, None, "acc-1")


# ─── update / delete ──────────────────────────────────────────────────────────


class TestRecipeServiceUpdate:
    @pytest.fixture
    def repo(self):
        repo = _make_repo()
        repo.get_by_id_with_relations.return_value = _owned_recipe()
        repo.apply_update.side_effect = lambda recipe, fields, ings: recipe
        return repo

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def service(self, repo, search):
        return RecipeService(repo, search, nutrition_client=_make_nutrition_client())

    async def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_id_with_relations.return_value = None
        with pytest.raises(RecipeNotFound):
            await service.update(1, RecipeUpdate(title="X"), "user-1")

    async def test_raises_forbidden_when_not_author(self, service, repo):
        repo.get_by_id_with_relations.return_value = _owned_recipe("someone-else")
        with pytest.raises(RecipeForbidden):
            await service.update(1, RecipeUpdate(title="X"), "user-1")

    async def test_only_sets_provided_fields(self, service, repo):
        await service.update(1, RecipeUpdate(comment="Excellent"), "user-1")
        _, fields, _ = repo.apply_update.call_args[0]
        assert fields == {"comment": "Excellent"}

    async def test_regenerates_slug_when_title_changes(self, service, repo):
        repo.slug_exists.return_value = False
        await service.update(1, RecipeUpdate(title="Nouveau Titre"), "user-1")
        _, fields, _ = repo.apply_update.call_args[0]
        assert fields["slug"] == "nouveau-titre"

    async def test_indexes_after_update(self, service, repo, search):
        await service.update(1, RecipeUpdate(comment="ok"), "user-1")
        search.index_recipe.assert_called_once()

    async def test_es_failure_does_not_raise(self, service, repo, search):
        search.index_recipe.side_effect = Exception("ES down")
        result = await service.update(1, RecipeUpdate(comment="ok"), "user-1")
        assert result is not None


class TestRecipeServiceDelete:
    @pytest.fixture
    def repo(self):
        repo = _make_repo()
        repo.get_by_id_with_relations.return_value = _owned_recipe()
        return repo

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def service(self, repo, search):
        return RecipeService(repo, search, nutrition_client=_make_nutrition_client())

    async def test_raises_not_found_when_missing(self, service, repo):
        repo.get_by_id_with_relations.return_value = None
        with pytest.raises(RecipeNotFound):
            await service.delete(1, "user-1")

    async def test_raises_forbidden_when_not_author(self, service, repo):
        repo.get_by_id_with_relations.return_value = _owned_recipe("someone-else")
        with pytest.raises(RecipeForbidden):
            await service.delete(1, "user-1")

    async def test_deletes_and_unindexes(self, service, repo, search):
        await service.delete(1, "user-1")
        repo.delete.assert_called_once()
        search.delete_recipe.assert_called_once_with(1)

    async def test_es_failure_does_not_raise(self, service, repo, search):
        search.delete_recipe.side_effect = Exception("ES down")
        await service.delete(1, "user-1")
        repo.delete.assert_called_once()


class TestRecipeServiceDeleteByUser:
    @pytest.fixture
    def repo(self):
        repo = AsyncMock()
        repo.delete_by_user.return_value = 3
        return repo

    @pytest.fixture
    def search(self):
        return _make_search()

    @pytest.fixture
    def service(self, repo, search):
        return RecipeService(repo, search, nutrition_client=_make_nutrition_client())

    async def test_deletes_user_recipes_and_unindexes(self, service, repo, search):
        deleted = await service.delete_by_user("user-1")
        assert deleted == 3
        repo.delete_by_user.assert_awaited_once_with("user-1")
        search.delete_by_user.assert_awaited_once_with("user-1")

    async def test_es_failure_does_not_raise(self, service, repo, search):
        search.delete_by_user.side_effect = Exception("ES down")
        deleted = await service.delete_by_user("user-1")
        assert deleted == 3
        repo.delete_by_user.assert_awaited_once_with("user-1")
