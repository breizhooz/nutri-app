import pytest
from datetime import date
from unittest.mock import MagicMock

from app.services.shopping_list_service import build_shopping_list


def _make_slot(recipe_id: int):
    slot = MagicMock()
    slot.recipe_id = recipe_id
    return slot


def _make_menu(slots, nb_persons=2, menu_id=1, slug="test-menu", start_date=None):
    menu = MagicMock()
    menu.id = menu_id
    menu.slug = slug
    menu.nb_persons = nb_persons
    menu.start_date = start_date or date(2026, 1, 6)
    menu.slots = slots
    return menu


def _make_client(recipes_by_id: dict):
    class _Client:
        async def get_recipe_by_id(self, recipe_id: int):
            return recipes_by_id.get(recipe_id)
    return _Client()


RECIPE_PASTA_EGG = {
    "id": 1,
    "recipe_ingredients": [
        {"ingredient_id": 10, "ingredient": {"id": 10, "name": "Pasta", "tags": ["enums.type.pasta"]}, "quantity": 200, "unit": "g"},
        {"ingredient_id": 11, "ingredient": {"id": 11, "name": "Egg",  "tags": []},                   "quantity": 3,   "unit": "unit"},
    ],
}

RECIPE_PASTA_ONLY = {
    "id": 2,
    "recipe_ingredients": [
        {"ingredient_id": 10, "ingredient": {"id": 10, "name": "Pasta", "tags": ["enums.type.pasta"]}, "quantity": 100, "unit": "g"},
    ],
}


class TestBuildShoppingList:
    async def test_aggregates_same_ingredient_across_slots(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1), _make_slot(2)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG, 2: RECIPE_PASTA_ONLY}),
        )
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.total_quantity == pytest.approx(300.0)

    async def test_multiplies_quantity_by_nb_persons(self):
        sl = await build_shopping_list(_make_menu([_make_slot(1)], nb_persons=3), _make_client({1: RECIPE_PASTA_EGG}))
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.total_quantity == pytest.approx(600.0)

    async def test_no_duplicate_ingredient_ids(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1), _make_slot(2)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG, 2: RECIPE_PASTA_ONLY}),
        )
        ids = [i.ingredient_id for i in sl.items]
        assert len(ids) == len(set(ids))

    async def test_missing_recipe_is_skipped(self):
        sl = await build_shopping_list(_make_menu([_make_slot(999)], nb_persons=1), _make_client({}))
        assert sl.items == []

    async def test_empty_slots_returns_empty_list(self):
        sl = await build_shopping_list(_make_menu([], nb_persons=2), _make_client({}))
        assert sl.items == []

    async def test_metadata_fields_set_correctly(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], menu_id=7, slug="my-menu", nb_persons=4, start_date=date(2026, 3, 10)),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        assert sl.menu_id == 7
        assert sl.menu_slug == "my-menu"
        assert sl.nb_persons == 4
        assert sl.start_date == date(2026, 3, 10)

    async def test_items_sorted_by_category_then_name(self):
        sl = await build_shopping_list(_make_menu([_make_slot(1)], nb_persons=1), _make_client({1: RECIPE_PASTA_EGG}))
        keys = [(i.category or "", i.ingredient_name) for i in sl.items]
        assert keys == sorted(keys)

    async def test_category_taken_from_first_tag(self):
        sl = await build_shopping_list(_make_menu([_make_slot(1)], nb_persons=1), _make_client({1: RECIPE_PASTA_EGG}))
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.category == "enums.type.pasta"

    async def test_no_tags_gives_none_category(self):
        sl = await build_shopping_list(_make_menu([_make_slot(1)], nb_persons=1), _make_client({1: RECIPE_PASTA_EGG}))
        egg = next(i for i in sl.items if i.ingredient_id == 11)
        assert egg.category is None

    async def test_quantity_rounded_to_two_decimals(self):
        recipe = {"id": 3, "recipe_ingredients": [
            {"ingredient_id": 20, "ingredient": {"id": 20, "name": "Oil", "tags": []}, "quantity": 1, "unit": "tbsp"}
        ]}
        sl = await build_shopping_list(_make_menu([_make_slot(3)] * 3, nb_persons=1), _make_client({3: recipe}))
        item = sl.items[0]
        assert item.total_quantity == round(item.total_quantity, 2)

    async def test_null_slug_uses_empty_string(self):
        sl = await build_shopping_list(_make_menu([_make_slot(1)], nb_persons=1, slug=None), _make_client({1: RECIPE_PASTA_EGG}))
        assert sl.menu_slug == ""