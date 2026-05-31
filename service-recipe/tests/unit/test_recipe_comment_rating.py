import pytest
from pydantic import ValidationError

from app.models.recipe import Recipe
from app.models.ingredient import Ingredient  # noqa: F401 (register mapper)
from app.schemas.recipe import RecipeUpdate

BASE = {
    "title": "Ma recette",
    "slug": "ma-recette",
    "instructions": "Bla bla bla",
}


class TestRecipeRatingModelValidator:
    @pytest.mark.parametrize("value", [1, 3, 5])
    def test_valid_rating_accepted(self, value):
        recipe = Recipe(**BASE, rating=value)
        assert recipe.rating == value

    def test_none_rating_accepted(self):
        recipe = Recipe(**BASE, rating=None, comment="Trop bon")
        assert recipe.rating is None
        assert recipe.comment == "Trop bon"

    @pytest.mark.parametrize("value", [0, 6, -1, 42])
    def test_out_of_range_rating_raises(self, value):
        with pytest.raises(ValueError, match="note valide"):
            Recipe(**BASE, rating=value)


class TestRecipeUpdateSchema:
    @pytest.mark.parametrize("value", [1, 5])
    def test_valid_rating_accepted(self, value):
        update = RecipeUpdate(rating=value, comment="Note")
        assert update.rating == value
        assert update.comment == "Note"

    @pytest.mark.parametrize("value", [0, 6])
    def test_out_of_range_rating_raises(self, value):
        with pytest.raises(ValidationError) as exc_info:
            RecipeUpdate(rating=value)
        assert any(e["loc"] == ("rating",) for e in exc_info.value.errors())
