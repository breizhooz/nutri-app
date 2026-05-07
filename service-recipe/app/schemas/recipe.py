from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any,  list
from datetime import datetime
from .recipe_ingredient import RecipeIngredientBase, RecipeIngredientResponse
from app.models.enums import (
    DifficultyLevel, RecipeOrigin, CuisineOrigin
)

class RecipeBase(BaseModel):
    title: str = Field(..., max_length=300)
    slug: str = Field(..., max_length=350)
    description: Optional[str] = None
    instructions: str
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servins: int = 4
    difficulty: DifficultyLevel = DifficultyLevel.EASY
    cuisine_origin: CuisineOrigin = CuisineOrigin.FRENCH
    origin_recipe: RecipeOrigin = RecipeOrigin.PERSONAL
    tags: dict[str, Any] = {}
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    created_by_user_id: Optional[int] = None

class RecipeCreate(RecipeBase):
    # Pour la création, on s'attend à recevoir une liste d'ingrédients (ID + quantité)
    recipe_ingredients: list[RecipeIngredientBase]

class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servins: Optional[int] = None # Toujours avec ta petite typo "servins" ;)
    difficulty: Optional[DifficultyLevel] = None
    cuisine_origin: Optional[CuisineOrigin] = None
    origin_recipe: Optional[RecipeOrigin] = None
    tags: Optional[dict[str, Any]] = None
    book_name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    recipe_ingredients: Optional[list[RecipeIngredientBase]] = None

    model_config = ConfigDict(from_attributes=True)

class RecipeResponse(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # On expose les ingrédients complets dans la réponse
    recipe_ingredients: list[RecipeIngredientResponse]
    
    model_config = ConfigDict(from_attributes=True)