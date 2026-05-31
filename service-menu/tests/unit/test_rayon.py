import pytest

from app.services.rayon import category_to_rayon

FRUIT = "enums.type_of_ingredient.fruit"
DAIRY = "enums.type_of_ingredient.dairy"
GRAIN = "enums.type_of_ingredient.grain"
DRINK = "enums.type_of_ingredient.drink"
OTHER = "enums.type_of_ingredient.other"


@pytest.mark.unit
class TestCategoryToRayon:
    def test_no_tags_returns_none(self):
        assert category_to_rayon([]) is None

    def test_only_non_type_tags_returns_none(self):
        # Allergènes / régimes ne portent pas d'info de rayon.
        assert category_to_rayon(["enums.allergen.milk", "enums.diet.vegan"]) is None

    def test_banane_maps_to_fruit(self):
        # Banane = fruit tropical -> rayon Fruits.
        assert category_to_rayon(["enums.type_of_ingredient.tropical_fruit"]) == FRUIT

    def test_skyr_maps_to_dairy(self):
        # Skyr = yaourt -> rayon Produits laitiers, même précédé d'un allergène.
        tags = ["enums.allergen.milk", "enums.type_of_ingredient.yogurt"]
        assert category_to_rayon(tags) == DAIRY

    @pytest.mark.parametrize(
        "subtype, expected",
        [
            ("white_meat", "enums.type_of_ingredient.meat"),
            ("smoked_fish", "enums.type_of_ingredient.fish"),
            ("cheese", DAIRY),
            ("citrus", FRUIT),
            ("root_vegetable", "enums.type_of_ingredient.vegetable"),
            ("pasta", GRAIN),
            ("oil", "enums.type_of_ingredient.fat"),
            ("spice", "enums.type_of_ingredient.herb"),
            ("sauce", "enums.type_of_ingredient.condiment"),
            ("wine", DRINK),
        ],
    )
    def test_subtypes_fold_into_parent_rayon(self, subtype, expected):
        assert category_to_rayon([f"enums.type_of_ingredient.{subtype}"]) == expected

    def test_unmapped_food_type_falls_back_to_other(self):
        # Un type d'aliment connu mais sans rayon dédié (ex: sucre) -> Divers.
        assert category_to_rayon(["enums.type_of_ingredient.sugar"]) == OTHER

    def test_first_food_type_tag_wins(self):
        tags = [
            "enums.type_of_ingredient.cheese",
            "enums.type_of_ingredient.fruit",
        ]
        assert category_to_rayon(tags) == DAIRY
