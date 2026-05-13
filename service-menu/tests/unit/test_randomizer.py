import pytest
from datetime import date

from tests.conftest import make_recipe, MockRecipeClient
from app.services.randomizer import (
    _calories_per_serving,
    _has_excluded_allergen,
    generate_slots,
)
from app.models.enums import Allergen, DayOfWeek, MealType


class TestCaloriesPerServing:
    def test_no_ingredients_returns_none(self):
        assert _calories_per_serving({"recipe_ingredients": [], "servings": 1}) is None

    def test_missing_ingredients_key_returns_none(self):
        assert _calories_per_serving({"servings": 1}) is None

    def test_ingredient_without_calories_key_returns_zero(self):
        recipe = make_recipe(1, cals_per_100g=None)
        assert _calories_per_serving(recipe) == pytest.approx(0.0)

    def test_basic_single_ingredient(self):
        recipe = make_recipe(1, cals_per_100g=200.0, qty=100, servings=1)
        assert _calories_per_serving(recipe) == pytest.approx(200.0)

    def test_divided_by_servings(self):
        recipe = make_recipe(1, cals_per_100g=100.0, qty=200, servings=2)
        assert _calories_per_serving(recipe) == pytest.approx(100.0)

    def test_missing_servings_defaults_to_one(self):
        recipe = {
            "recipe_ingredients": [
                {"ingredient": {"calories_per_100g": 100.0}, "quantity": 100}
            ]
        }
        assert _calories_per_serving(recipe) == pytest.approx(100.0)

    def test_multiple_ingredients_summed(self):
        recipe = {
            "servings": 1,
            "recipe_ingredients": [
                {"ingredient": {"calories_per_100g": 100.0}, "quantity": 100},
                {"ingredient": {"calories_per_100g": 200.0}, "quantity": 50},
            ],
        }
        assert _calories_per_serving(recipe) == pytest.approx(200.0)


class TestHasExcludedAllergen:
    def test_empty_exclusions_always_false(self):
        recipe = make_recipe(1, allergens=["enums.allergen.gluten"])
        assert _has_excluded_allergen(recipe, set()) is False

    def test_matching_allergen_returns_true(self):
        recipe = make_recipe(1, allergens=["enums.allergen.gluten"])
        assert _has_excluded_allergen(recipe, {"enums.allergen.gluten"}) is True

    def test_non_matching_allergen_returns_false(self):
        recipe = make_recipe(1, allergens=["enums.allergen.milk"])
        assert _has_excluded_allergen(recipe, {"enums.allergen.gluten"}) is False

    def test_no_ingredient_tags(self):
        recipe = make_recipe(1, allergens=[])
        assert _has_excluded_allergen(recipe, {"enums.allergen.gluten"}) is False

    def test_no_recipe_ingredients(self):
        assert _has_excluded_allergen({"recipe_ingredients": []}, {"enums.allergen.gluten"}) is False

    def test_multiple_allergens_one_matches(self):
        recipe = make_recipe(1, allergens=["enums.allergen.milk"])
        assert _has_excluded_allergen(recipe, {"enums.allergen.gluten", "enums.allergen.milk"}) is True


class TestGenerateSlots:
    def _client(self, recipes):
        return MockRecipeClient(recipes)

    async def test_default_produces_14_slots(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 25)]),
            nb_persons=2, start_date=date(2026, 1, 6), exclusions=[],
        )
        assert len(slots) == 14

    async def test_all_seven_days_covered(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 25)]),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[],
        )
        assert {s.day_of_week for s in slots} == set(DayOfWeek)

    async def test_default_meal_types_are_lunch_and_dinner(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 25)]),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[],
        )
        types = {s.meal_type for s in slots}
        assert MealType.LUNCH in types
        assert MealType.DINNER in types
        assert MealType.BREAKFAST not in types

    async def test_custom_single_meal_type(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 25)]),
            nb_persons=1, start_date=date(2026, 1, 6),
            exclusions=[], meal_types=[MealType.LUNCH],
        )
        assert len(slots) == 7
        assert all(s.meal_type == MealType.LUNCH for s in slots)

    async def test_three_meal_types_produces_21_slots(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 30)]),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[],
            meal_types=[MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER],
        )
        assert len(slots) == 21

    async def test_exclusion_filters_allergen_recipes(self):
        gluten = [make_recipe(i, allergens=["enums.allergen.gluten"]) for i in range(1, 5)]
        safe = [make_recipe(i) for i in range(10, 35)]
        slots = await generate_slots(
            self._client(gluten + safe),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[Allergen.GLUTEN],
        )
        gluten_ids = {r["id"] for r in gluten}
        assert all(s.recipe_id not in gluten_ids for s in slots)

    async def test_raises_when_all_recipes_excluded(self):
        gluten_only = [make_recipe(i, allergens=["enums.allergen.gluten"]) for i in range(1, 5)]
        with pytest.raises(ValueError, match="Aucune recette"):
            await generate_slots(
                self._client(gluten_only),
                nb_persons=1, start_date=date(2026, 1, 6), exclusions=[Allergen.GLUTEN],
            )

    async def test_pool_repeats_when_fewer_recipes_than_slots(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 4)]),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[],
        )
        assert len(slots) == 14

    async def test_caloric_soft_filter_applied_when_pool_large_enough(self):
        high = [make_recipe(i, cals_per_100g=1000.0, qty=100, servings=1) for i in range(1, 50)]
        low  = [make_recipe(i + 100, cals_per_100g=50.0, qty=100, servings=1) for i in range(1, 50)]
        slots = await generate_slots(
            self._client(high + low),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[], caloric_target=500,
        )
        assert all(s.recipe_id > 100 for s in slots)

    async def test_caloric_filter_skipped_when_not_enough_fitting(self):
        high = [make_recipe(i, cals_per_100g=1000.0, qty=100, servings=1) for i in range(1, 50)]
        low  = [make_recipe(i + 100, cals_per_100g=50.0, qty=100, servings=1) for i in range(1, 6)]
        slots = await generate_slots(
            self._client(high + low),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[], caloric_target=500,
        )
        assert any(s.recipe_id < 100 for s in slots)

    async def test_custom_duration(self):
        slots = await generate_slots(
            self._client([make_recipe(i) for i in range(1, 25)]),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[], duration_days=3,
        )
        assert len(slots) == 6

    async def test_slot_recipe_ids_are_valid(self):
        recipes = [make_recipe(i) for i in range(1, 25)]
        valid_ids = {r["id"] for r in recipes}
        slots = await generate_slots(
            self._client(recipes),
            nb_persons=1, start_date=date(2026, 1, 6), exclusions=[],
        )
        assert all(s.recipe_id in valid_ids for s in slots)
        