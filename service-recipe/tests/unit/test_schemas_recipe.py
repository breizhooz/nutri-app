import pytest
from pydantic import ValidationError
from app.schemas.recipe import RecipeCreate
from app.models.enums import RecipeOrigin

BASE = {
    "title": "Ma recette",
    "instructions": "Bla bla bla",
    "recipe_ingredients": [],
}

class TestRecipeCreateValidator:

    def test_book_origin_without_name_raises(self):
        """origin=BOOK witout book name need to raise validationError"""
        with pytest.raises(ValidationError) as exc_info:
            RecipeCreate(**BASE, origin_recipe=RecipeOrigin.BOOK, book_name=None)

            errors = exc_info.value.errors()
            assert any(e["loc"] == ("book_name",) for e in errors)

    def test_book_origin_with_book_name_is_valid(self):
        """origin=BOOK avec book_name ne doit pas lever d'erreur"""
        recipe = RecipeCreate(
            **BASE,
            origin_recipe=RecipeOrigin.BOOK,
            book_name="Larousse Gastronomique",
        )
        assert recipe.book_name == "Larousse Gastronomique"
    
    def test_personnal_origin_without_book_name(self):
        recipe = RecipeCreate(
            **BASE,
            origin_recipe = RecipeOrigin.PERSONAL,
        )
        assert recipe.book_name is None
    

