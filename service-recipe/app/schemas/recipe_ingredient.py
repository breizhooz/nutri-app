from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from .ingredient import IngredientResponse

class RecipeIngredientBase(BaseModel):
    ingredient_id: int
    quantity: float
    unit: str = Field(..., max_length=50)

class RecipeIngredientCreate(RecipeIngredientBase):
    pass

class RecipeIngredientResponse(RecipeIngredientBase):
    id: int
    # On inclut l'objet ingrédient pour avoir le nom et les tags au lieu d'un simple ID
    ingredient: IngredientResponse 
    model_config = ConfigDict(from_attributes=True)