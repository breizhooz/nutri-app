from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import Optional, Any, Union, List
from app.models.enums import (
    TypeOfIngredient, Allergen, Nutrition, Diet
)

class IngredientBase(BaseModel):
    name: str = Field(..., max_length=200)
    tags: List[Union[TypeOfIngredient, Allergen, Nutrition, Diet]] = []
    free_tags: list[str] = []
    calories_per_100g: Optional[float] = None
    proteins_per_100g: Optional[float] = None
    carbs_per_100g: Optional[float] = None
    fats_per_100g: Optional[float] = None

class IngredientCreate(IngredientBase):
    pass

class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[Union[TypeOfIngredient, Allergen, Nutrition, Diet]]] = None
    free_tags: Optional[list[str]] = None
    calories_per_100g: Optional[float] = None
    proteins_per_100g: Optional[float] = None
    carbs_per_100g: Optional[float] = None
    fats_per_100g: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class IngredientResponse(IngredientBase):
    id: int
    model_config = ConfigDict(from_attributes=True)