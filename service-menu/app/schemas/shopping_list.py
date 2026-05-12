from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date


class ShoppingItem(BaseModel):
    ingredient_id: int
    ingredient_name: str
    total_quantity: float = Field(ge=0)
    unit: str
    category: Optional[str] = None  # TypeOfIngredient.value pour grouper en rayon

    model_config = ConfigDict(from_attributes=True)


class ShoppingList(BaseModel):
    menu_id: int
    menu_slug: str
    nb_persons: int
    start_date: date
    items: list[ShoppingItem]

    model_config = ConfigDict(from_attributes=True)