"""Tests du mapping profil → contraintes et de son application au randomizer."""

from datetime import date

from tests.conftest import make_recipe, MockRecipeClient
from app.models.enums import Allergen
from app.services.profile_constraints import (
    ProfileConstraints,
    build_constraints,
)
from app.services.randomizer import generate_slots


def _summary(
    allergies: list[str] | None = None,
    excluded_foods: list[str] | None = None,
    prefs_excluded: list[str] | None = None,
    diet_type: str | None = None,
    target_calories: int | None = None,
) -> dict:
    """Résumé nutritionnel minimal au format service-profile."""
    summary: dict = {
        "user_id": "u-1",
        "allergies": [
            {"slug": f"a-{i}", "allergen": a, "severity": "allergy"}
            for i, a in enumerate(allergies or [])
        ],
        "excluded_foods": [
            {"slug": f"e-{i}", "food_name": n}
            for i, n in enumerate(excluded_foods or [])
        ],
        "nutrition_preferences": None,
        "calculation": None,
    }
    if diet_type or prefs_excluded:
        summary["nutrition_preferences"] = {
            "diet_type": diet_type,
            "excluded_foods": prefs_excluded or [],
        }
    if target_calories is not None:
        summary["calculation"] = {"target_calories_kcal": target_calories}
    return summary


class TestBuildConstraints:
    def test_none_summary_gives_empty_constraints(self):
        c = build_constraints(None)
        assert c.excluded_tags == frozenset()
        assert c.excluded_food_terms == frozenset()
        assert c.target_calories is None

    def test_allergy_fr_label_maps_to_allergen_tag(self):
        c = build_constraints(_summary(allergies=["Arachides"]))
        assert Allergen.PEANUTS.value in c.allergen_tags

    def test_allergy_en_label_maps_to_allergen_tag(self):
        c = build_constraints(_summary(allergies=["peanut"]))
        assert Allergen.PEANUTS.value in c.allergen_tags

    def test_allergy_accented_label_maps(self):
        c = build_constraints(_summary(allergies=["Céleri"]))
        assert Allergen.CELERY.value in c.allergen_tags

    def test_allergy_label_always_added_as_food_term(self):
        # Défense en profondeur : même mappée, l'allergie exclut aussi par nom.
        c = build_constraints(_summary(allergies=["lait"]))
        assert Allergen.MILK.value in c.allergen_tags
        assert "lait" in c.excluded_food_terms

    def test_unmapped_allergy_falls_back_to_food_term(self):
        c = build_constraints(_summary(allergies=["kiwi"]))
        assert c.allergen_tags == frozenset()
        assert "kiwi" in c.excluded_food_terms

    def test_excluded_foods_from_both_sources_merged(self):
        c = build_constraints(
            _summary(excluded_foods=["Champignon"], prefs_excluded=["Brocoli"])
        )
        assert "champignon" in c.excluded_food_terms
        assert "brocoli" in c.excluded_food_terms

    def test_vegan_diet_forbids_animal_tags(self):
        c = build_constraints(_summary(diet_type="vegan"))
        assert "enums.type_of_ingredient.red_meat" in c.forbidden_tags
        assert "enums.type_of_ingredient.fish" in c.forbidden_tags
        assert "enums.type_of_ingredient.milk" in c.forbidden_tags
        assert "enums.type_of_ingredient.egg" in c.forbidden_tags
        assert "enums.type_of_ingredient.honey" in c.forbidden_tags

    def test_vegetarian_allows_dairy_and_eggs(self):
        c = build_constraints(_summary(diet_type="vegetarian"))
        assert "enums.type_of_ingredient.meat" in c.forbidden_tags
        assert "enums.type_of_ingredient.milk" not in c.forbidden_tags
        assert "enums.type_of_ingredient.egg" not in c.forbidden_tags

    def test_no_pork_diet_excludes_pork_by_name(self):
        c = build_constraints(_summary(diet_type="no_pork"))
        assert c.forbidden_tags == frozenset()
        assert "porc" in c.excluded_food_terms
        assert "jambon" in c.excluded_food_terms

    def test_halal_diet_forbids_alcohol_tags_and_pork_terms(self):
        c = build_constraints(_summary(diet_type="halal"))
        assert "enums.type_of_ingredient.alcohol" in c.forbidden_tags
        assert "porc" in c.excluded_food_terms

    def test_omnivore_diet_adds_no_constraint(self):
        c = build_constraints(_summary(diet_type="omnivore"))
        assert c.forbidden_tags == frozenset()
        assert c.excluded_food_terms == frozenset()

    def test_target_calories_extracted(self):
        c = build_constraints(_summary(target_calories=2200))
        assert c.target_calories == 2200


class TestMatchesExcludedName:
    def _c(self, *terms: str) -> ProfileConstraints:
        return ProfileConstraints(excluded_food_terms=frozenset(terms))

    def test_word_boundary_lait_does_not_match_laitue(self):
        c = self._c("lait")
        assert c.matches_excluded_name("Lait entier") is True
        assert c.matches_excluded_name("Laitue romaine") is False

    def test_accent_insensitive(self):
        assert self._c("celeri").matches_excluded_name("Céleri branche") is True

    def test_naive_plural_tolerated(self):
        assert (
            self._c("champignon").matches_excluded_name("Champignons de Paris") is True
        )

    def test_multi_word_term(self):
        assert (
            self._c("fruits a coque").matches_excluded_name("Mélange fruits à coque")
            is True
        )

    def test_empty_terms_never_match(self):
        assert ProfileConstraints().matches_excluded_name("Poulet") is False


class TestGenerateSlotsWithConstraints:
    async def test_profile_allergen_tags_filter_recipes(self):
        gluten = [
            make_recipe(i, allergens=["enums.allergen.gluten"]) for i in range(1, 5)
        ]
        safe = [make_recipe(i) for i in range(10, 35)]
        constraints = ProfileConstraints(
            allergen_tags=frozenset({"enums.allergen.gluten"})
        )
        slots = await generate_slots(
            MockRecipeClient(gluten + safe),
            nb_persons=1,
            start_date=date(2026, 1, 6),
            exclusions=[],
            constraints=constraints,
        )
        gluten_ids = {r["id"] for r in gluten}
        assert all(s.recipe_id not in gluten_ids for s in slots)

    async def test_diet_forbidden_tags_filter_recipes(self):
        meat = [
            make_recipe(i, allergens=["enums.type_of_ingredient.red_meat"])
            for i in range(1, 5)
        ]
        safe = [make_recipe(i) for i in range(10, 35)]
        constraints = build_constraints(_summary(diet_type="vegetarian"))
        slots = await generate_slots(
            MockRecipeClient(meat + safe),
            nb_persons=1,
            start_date=date(2026, 1, 6),
            exclusions=[],
            constraints=constraints,
        )
        meat_ids = {r["id"] for r in meat}
        assert all(s.recipe_id not in meat_ids for s in slots)

    async def test_excluded_food_name_filters_recipes(self):
        pork = make_recipe(1)
        pork["recipe_ingredients"][0]["ingredient"]["name"] = "Jambon blanc"
        safe = [make_recipe(i) for i in range(10, 35)]
        constraints = build_constraints(_summary(diet_type="no_pork"))
        slots = await generate_slots(
            MockRecipeClient([pork] + safe),
            nb_persons=1,
            start_date=date(2026, 1, 6),
            exclusions=[],
            constraints=constraints,
        )
        assert all(s.recipe_id != pork["id"] for s in slots)

    async def test_payload_and_profile_exclusions_are_merged(self):
        gluten = [make_recipe(1, allergens=["enums.allergen.gluten"])]
        milk = [make_recipe(2, allergens=["enums.allergen.milk"])]
        safe = [make_recipe(i) for i in range(10, 35)]
        constraints = ProfileConstraints(
            allergen_tags=frozenset({"enums.allergen.milk"})
        )
        slots = await generate_slots(
            MockRecipeClient(gluten + milk + safe),
            nb_persons=1,
            start_date=date(2026, 1, 6),
            exclusions=[Allergen.GLUTEN],
            constraints=constraints,
        )
        assert all(s.recipe_id not in {1, 2} for s in slots)

    async def test_no_constraints_keeps_legacy_behaviour(self):
        recipes = [make_recipe(i) for i in range(1, 25)]
        slots = await generate_slots(
            MockRecipeClient(recipes),
            nb_persons=2,
            start_date=date(2026, 1, 6),
            exclusions=[],
            constraints=None,
        )
        assert len(slots) == 35
