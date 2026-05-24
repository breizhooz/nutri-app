"""Tests unitaires pour le TypeOfIngredient enum."""

import pytest

from app.models.enums.food import TypeOfIngredient


class TestTypeOfIngredient:
    @pytest.mark.unit
    def test_enum_has_meat_value(self):
        """MEAT est défini avec la bonne valeur."""
        assert TypeOfIngredient.MEAT == "enums.type_of_ingredient.meat"

    @pytest.mark.unit
    def test_enum_is_string_subclass(self):
        """TypeOfIngredient étend str : les valeurs sont comparables à des chaînes."""
        assert isinstance(TypeOfIngredient.FISH, str)
        assert TypeOfIngredient.FISH == "enums.type_of_ingredient.fish"

    @pytest.mark.unit
    def test_all_values_start_with_prefix(self):
        """Toutes les valeurs commencent par 'enums.type_of_ingredient.'"""
        for member in TypeOfIngredient:
            assert member.value.startswith("enums.type_of_ingredient."), (
                f"{member.name} ne respecte pas le préfixe attendu"
            )

    @pytest.mark.unit
    def test_enum_lookup_by_value(self):
        """On peut retrouver un membre par sa valeur."""
        assert (
            TypeOfIngredient("enums.type_of_ingredient.dairy") == TypeOfIngredient.DAIRY
        )

    @pytest.mark.unit
    def test_invalid_value_raises(self):
        """Une valeur inconnue lève ValueError."""
        with pytest.raises(ValueError):
            TypeOfIngredient("not_a_valid_value")

    @pytest.mark.unit
    def test_enum_count_is_complete(self):
        """L'enum contient le nombre attendu de membres (aucune suppression accidentelle)."""
        assert len(TypeOfIngredient) >= 50

    @pytest.mark.unit
    def test_subcategories_present(self):
        """Les sous-catégories clés sont toutes présentes."""
        expected = {
            TypeOfIngredient.WHITE_MEAT,
            TypeOfIngredient.FATTY_FISH,
            TypeOfIngredient.LEAFY_VEGETABLE,
            TypeOfIngredient.TROPICAL_FRUIT,
            TypeOfIngredient.PSEUDO_GRAIN,
        }
        for item in expected:
            assert item in TypeOfIngredient

    @pytest.mark.unit
    def test_alcohol_subcategories(self):
        """Les sous-catégories alcool sont bien présentes."""
        assert TypeOfIngredient.WINE in TypeOfIngredient
        assert TypeOfIngredient.BEER in TypeOfIngredient
        assert TypeOfIngredient.SPIRIT in TypeOfIngredient

    @pytest.mark.unit
    def test_processed_food_categories(self):
        """Les catégories d'aliments transformés sont présentes."""
        assert TypeOfIngredient.CANNED in TypeOfIngredient
        assert TypeOfIngredient.FROZEN in TypeOfIngredient
        assert TypeOfIngredient.PREPARED in TypeOfIngredient
