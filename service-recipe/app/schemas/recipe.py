import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Any,  List
from datetime import datetime
from .recipe_ingredient import RecipeIngredientBase, RecipeIngredientResponse
from app.models.enums import (
    DifficultyLevel, RecipeOrigin, CuisineOrigin, CourseType
)

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
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    created_by_user_id: Optional[uuid.UUID] = None

class RecipeCreate(RecipeBase):
    # Pour la création, on s'attend à recevoir une liste d'ingrédients (ID + quantité)
    recipe_ingredients: List[RecipeIngredientBase]

    @field_validator('book_name')
    @classmethod
    def validate_book_name(cls, v, info):
        """book_name require if origin==book"""
        if info.data.get('origin_recipe') == RecipeOrigin.BOOK and v is None:
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
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    recipe_ingredients: Optional[List[RecipeIngredientBase]] = None

    model_config = ConfigDict(from_attributes=True)

class RecipeResponse(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # On expose les ingrédients complets dans la réponse
    recipe_ingredients: List[RecipeIngredientResponse]
    
    model_config = ConfigDict(from_attributes=True)