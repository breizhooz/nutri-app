"""Tests for coach→client recipe push (RecipeService.push_to_account)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import RecipeForbidden
from app.models.enums import CourseType, CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.models.recipe import Recipe
from app.services.recipe_service import RecipeService

SOURCE_ACCOUNT = "11111111-1111-1111-1111-111111111111"
TARGET_ACCOUNT = "22222222-2222-2222-2222-222222222222"


def _make_source(recipe_id: int = 7) -> MagicMock:
    src = MagicMock()
    src.id = recipe_id
    src.title = "Tarte aux pommes"
    src.account_id = SOURCE_ACCOUNT
    # Colonnes enum validées à la construction du modèle Recipe.
    src.difficulty = list(DifficultyLevel)[0]
    src.cuisine_origin = list(CuisineOrigin)[0]
    src.origin_recipe = list(RecipeOrigin)[0]
    src.course_type = list(CourseType)[0]
    src.tags = {}
    src.free_tags = []
    src.rating = None
    src.comment = None
    src.calories_per_serving = 123.0
    src.proteins_per_serving = 9.0
    src.carbs_per_serving = 30.0
    src.fats_per_serving = 4.0
    src.recipe_ingredients = []
    return src


def _make_service(repo: AsyncMock) -> RecipeService:
    search = AsyncMock()
    search.index_recipe.return_value = None
    return RecipeService(repo, search, AsyncMock(), AsyncMock())


@pytest.mark.asyncio
async def test_push_clones_recipe_into_target_account() -> None:
    src = _make_source(7)
    repo = AsyncMock()
    repo.get_by_id_with_relations.return_value = src
    repo.find_clone.return_value = None
    repo.slug_exists.return_value = False
    repo.create.side_effect = lambda recipe, ingredients: recipe  # echoes the clone

    service = _make_service(repo)
    created, skipped = await service.push_to_account(
        [7], SOURCE_ACCOUNT, TARGET_ACCOUNT
    )

    assert skipped == []
    assert len(created) == 1
    clone: Recipe = repo.create.call_args.args[0]
    assert clone.account_id == TARGET_ACCOUNT
    assert clone.source_recipe_id == 7
    assert clone.title == "Tarte aux pommes"
    # Macros recopiées telles quelles (copie one-shot).
    assert clone.calories_per_serving == 123.0
    assert clone.proteins_per_serving == 9.0


@pytest.mark.asyncio
async def test_push_skips_already_pushed_recipe() -> None:
    src = _make_source(7)
    repo = AsyncMock()
    repo.get_by_id_with_relations.return_value = src
    repo.find_clone.return_value = MagicMock()  # déjà poussée

    service = _make_service(repo)
    created, skipped = await service.push_to_account(
        [7], SOURCE_ACCOUNT, TARGET_ACCOUNT
    )

    assert created == []
    assert skipped == [7]
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_push_rejects_recipe_not_in_source_account() -> None:
    src = _make_source(7)
    src.account_id = "99999999-9999-9999-9999-999999999999"  # autre compte
    repo = AsyncMock()
    repo.get_by_id_with_relations.return_value = src

    service = _make_service(repo)
    with pytest.raises(RecipeForbidden):
        await service.push_to_account([7], SOURCE_ACCOUNT, TARGET_ACCOUNT)
