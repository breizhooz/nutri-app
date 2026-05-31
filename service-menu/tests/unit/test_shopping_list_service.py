import pytest
from datetime import date
from unittest.mock import MagicMock

from app.services.shopping_list_service import build_shopping_list


def _make_slot(recipe_id: int, nb_persons: int | None = None):
    slot = MagicMock()
    slot.recipe_id = recipe_id
    slot.nb_persons = nb_persons
    return slot


def _make_menu(slots, nb_persons=2, menu_id=1, slug="test-menu", start_date=None):
    menu = MagicMock()
    menu.id = menu_id
    menu.slug = slug
    menu.nb_persons = nb_persons
    menu.start_date = start_date or date(2026, 1, 6)
    # Par défaut, chaque slot hérite du nb_persons du menu (comme en base après backfill).
    for s in slots:
        if s.nb_persons is None:
            s.nb_persons = nb_persons
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
        {
            "ingredient_id": 10,
            "ingredient": {
                "id": 10,
                "name": "Pasta",
                "tags": ["enums.type_of_ingredient.pasta"],
            },
            "quantity": 200,
            "unit": "g",
        },
        {
            "ingredient_id": 11,
            "ingredient": {"id": 11, "name": "Egg", "tags": []},
            "quantity": 3,
            "unit": "unit",
        },
    ],
}

RECIPE_PASTA_ONLY = {
    "id": 2,
    "recipe_ingredients": [
        {
            "ingredient_id": 10,
            "ingredient": {
                "id": 10,
                "name": "Pasta",
                "tags": ["enums.type_of_ingredient.pasta"],
            },
            "quantity": 100,
            "unit": "g",
        },
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
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], nb_persons=3),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.total_quantity == pytest.approx(600.0)

    async def test_quantities_scaled_by_recipe_servings(self):
        # Recette pour 4 personnes : 800g de pâtes -> pour 2 pers = 800 * 2/4 = 400
        recipe = {
            "id": 5,
            "servings": 4,
            "recipe_ingredients": [
                {
                    "ingredient_id": 10,
                    "ingredient": {"id": 10, "name": "Pasta", "tags": []},
                    "quantity": 800,
                    "unit": "g",
                }
            ],
        }
        sl = await build_shopping_list(
            _make_menu([_make_slot(5, nb_persons=2)], nb_persons=2),
            _make_client({5: recipe}),
        )
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.total_quantity == pytest.approx(400.0)

    async def test_per_slot_nb_persons_scales_independently(self):
        # Pasta : slot1 (200g x2) + slot2 (100g x4) = 400 + 400 = 800
        sl = await build_shopping_list(
            _make_menu(
                [_make_slot(1, nb_persons=2), _make_slot(2, nb_persons=4)],
                nb_persons=2,
            ),
            _make_client({1: RECIPE_PASTA_EGG, 2: RECIPE_PASTA_ONLY}),
        )
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.total_quantity == pytest.approx(800.0)

    async def test_no_duplicate_ingredient_ids(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1), _make_slot(2)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG, 2: RECIPE_PASTA_ONLY}),
        )
        ids = [i.ingredient_id for i in sl.items]
        assert len(ids) == len(set(ids))

    async def test_missing_recipe_is_skipped(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(999)], nb_persons=1), _make_client({})
        )
        assert sl.items == []

    async def test_empty_slots_returns_empty_list(self):
        sl = await build_shopping_list(_make_menu([], nb_persons=2), _make_client({}))
        assert sl.items == []

    async def test_metadata_fields_set_correctly(self):
        sl = await build_shopping_list(
            _make_menu(
                [_make_slot(1)],
                menu_id=7,
                slug="my-menu",
                nb_persons=4,
                start_date=date(2026, 3, 10),
            ),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        assert sl.menu_id == 7
        assert sl.menu_slug == "my-menu"
        assert sl.nb_persons == 4
        assert sl.start_date == date(2026, 3, 10)

    async def test_items_sorted_by_category_then_name(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        keys = [(i.category or "", i.ingredient_name) for i in sl.items]
        assert keys == sorted(keys)

    async def test_category_normalized_to_coarse_rayon(self):
        # "pasta" est un sous-type de TypeOfIngredient -> rayon « Céréales & féculents ».
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        pasta = next(i for i in sl.items if i.ingredient_id == 10)
        assert pasta.category == "enums.type_of_ingredient.grain"

    async def test_no_tags_gives_none_category(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], nb_persons=1),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        egg = next(i for i in sl.items if i.ingredient_id == 11)
        assert egg.category is None

    async def test_quantity_rounded_to_two_decimals(self):
        recipe = {
            "id": 3,
            "recipe_ingredients": [
                {
                    "ingredient_id": 20,
                    "ingredient": {"id": 20, "name": "Oil", "tags": []},
                    "quantity": 1,
                    "unit": "tbsp",
                }
            ],
        }
        sl = await build_shopping_list(
            _make_menu([_make_slot(3)] * 3, nb_persons=1), _make_client({3: recipe})
        )
        item = sl.items[0]
        assert item.total_quantity == round(item.total_quantity, 2)

    async def test_null_slug_uses_empty_string(self):
        sl = await build_shopping_list(
            _make_menu([_make_slot(1)], nb_persons=1, slug=None),
            _make_client({1: RECIPE_PASTA_EGG}),
        )
        assert sl.menu_slug == ""
