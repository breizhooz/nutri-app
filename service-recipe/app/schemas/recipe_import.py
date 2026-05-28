from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Any

from app.models.enums import (
    DifficultyLevel,
    RecipeOrigin,
    CuisineOrigin,
    CourseType,
    TypeOfIngredient,
    Allergen,
    Nutrition,
    Diet,
)

_ALLOWED_INGREDIENT_TAGS = {
    *(e.value for e in TypeOfIngredient),
    *(e.value for e in Allergen),
    *(e.value for e in Nutrition),
    *(e.value for e in Diet),
}


class IngredientImport(BaseModel):
    """Ingredient of the catalog, upserted by name with its nutrition values."""

    name: str = Field(..., max_length=200)
    tags: list[str] = []
    free_tags: list[str] = []
    calories_per_100g: Optional[float] = None
    proteins_per_100g: Optional[float] = None
    carbs_per_100g: Optional[float] = None
    fats_per_100g: Optional[float] = None

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        invalid = [t for t in value if t not in _ALLOWED_INGREDIENT_TAGS]
        if invalid:
            raise ValueError(
                f"tags invalides {invalid} — valeurs attendues parmi "
                "TypeOfIngredient, Allergen, Nutrition ou Diet."
            )
        return value


class RecipeIngredientImport(BaseModel):
    """Reference to a catalog ingredient by name, with its quantity in the recipe."""

    name: str = Field(..., max_length=200)
    quantity: float
    unit: str = Field(default="g", max_length=50)


class RecipeImportItem(BaseModel):
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    instructions: str = ""
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: int = 4
    difficulty: DifficultyLevel = DifficultyLevel.EASY
    cuisine_origin: CuisineOrigin = CuisineOrigin.FRENCH
    origin_recipe: RecipeOrigin = RecipeOrigin.PERSONAL
    course_type: CourseType = CourseType.MAIN_COURSE
    tags: dict[str, Any] = {}
    free_tags: list[str] = []
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    ingredients: list[RecipeIngredientImport] = []


class RecipeImportPayload(BaseModel):
    created_by_user_id: str
    ingredients: list[IngredientImport] = []
    recipes: list[RecipeImportItem] = []

    @model_validator(mode="after")
    def _check_recipe_ingredients_in_catalog(self) -> "RecipeImportPayload":
        catalog = {ing.name for ing in self.ingredients}
        missing: dict[str, set[str]] = {}
        for recipe in self.recipes:
            for ri in recipe.ingredients:
                if ri.name not in catalog:
                    missing.setdefault(recipe.title, set()).add(ri.name)
        if missing:
            details = "; ".join(
                f"'{title}' → {sorted(names)}" for title, names in missing.items()
            )
            raise ValueError(
                "Ingrédients référencés absents du catalogue racine : " + details
            )
        return self
