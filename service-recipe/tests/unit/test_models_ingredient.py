import pytest
from app.models.ingredient import Ingredient
from app.models.enums import TypeOfIngredient, Allergen

class TestIngredientTagsValidator:

    def test_valid_tags_accepted(self):
        """check if tags from enum allowed doesn't raise any error"""
        ingredient = Ingredient(
            name="Thon",
            tags=[TypeOfIngredient.FISH.value, Allergen.FISH.value]
        )
        assert TypeOfIngredient.FISH.value in ingredient.tags
    
    def test_invalid_tag_raises_value_error(self):
        """tag unknow have raise valueError"""
        with pytest.raises(ValueError, match="not valid"):
            Ingredient(name="toto", tags=["not implement"])
    
    def test_empty_tags_accepted(self):
        """empty tags accepted"""
        ingredient = Ingredient(name="toto",tags=[])
        assert ingredient.tags == []

    def test_mixed_enum_types_accepted(self):
        from app.models.enums import Diet, Nutrition
        ingredient = Ingredient(
            name="toto",
            tags = [
                Diet.VEGAN.value,
                TypeOfIngredient.MEAT.value,
                Nutrition.HIGH_CALORIE.value,
            ]
            )
        
        assert len(ingredient.tags) == 3