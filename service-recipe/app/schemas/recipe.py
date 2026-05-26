from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Any, List
from datetime import datetime
from .recipe_ingredient import RecipeIngredientBase, RecipeIngredientResponse
from app.models.enums import DifficultyLevel, RecipeOrigin, CuisineOrigin, CourseType


class RecipeBase(BaseModel):
    title: str = Field(..., max_length=300)
    slug: str | None = Field(default=None, max_length=350)
    description: Optional[str] = None
    instructions: str
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
    created_by_user_id: Optional[str] = None
    calories_per_serving: Optional[float] = None
    proteins_per_serving: Optional[float] = None
    carbs_per_serving: Optional[float] = None
    fats_per_serving: Optional[float] = None


class RecipeCreate(RecipeBase):
    # Pour la création, on s'attend à recevoir une liste d'ingrédients (ID + quantité)
    recipe_ingredients: List[RecipeIngredientBase]

    @field_validator("book_name")
    @classmethod
    def validate_book_name(cls, v, info):
        """book_name require if origin==book"""
        if info.data.get("origin_recipe") == RecipeOrigin.BOOK and v is None:
            raise ValueError("book_name is require when origin = book")
        return v


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[DifficultyLevel] = None
    cuisine_origin: Optional[CuisineOrigin] = None
    origin_recipe: Optional[RecipeOrigin] = None
    course_type: Optional[CourseType] = None
    tags: Optional[dict[str, Any]] = None
    free_tags: Optional[list[str]] = None
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    recipe_ingredients: Optional[List[RecipeIngredientBase]] = None
    calories_per_serving: Optional[float] = None
    proteins_per_serving: Optional[float] = None
    carbs_per_serving: Optional[float] = None
    fats_per_serving: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class RecipeResponse(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # On expose les ingrédients complets dans la réponse
    recipe_ingredients: List[RecipeIngredientResponse]

    model_config = ConfigDict(from_attributes=True)


class PaginatedRecipeResponse(BaseModel):
    items: List[RecipeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ManualIngredient(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "g"


class RecipeManualCreate(BaseModel):
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    instructions: str = ""
    servings: int = 4
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    course_type: Optional[CourseType] = None
    free_tags: list[str] = []
    ingredients: list[ManualIngredient] = []
