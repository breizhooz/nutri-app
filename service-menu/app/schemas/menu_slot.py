from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.enums import (
    DayOfWeek, MealType
)

class MenuSlotBase(BaseModel):
    day_of_week: DayOfWeek = DayOfWeek.MONDAY
    meal_type: MealType = MealType.BREAKFAST
    recipe_id: int

class MenuSlotCreate(MenuSlotBase):
    pass

class MenuSlotUpdate(BaseModel):
    day_of_week: Optional[DayOfWeek] = None
    meal_type: Optional[MealType] = None
    recipe_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class MenuSlotResponse(MenuSlotBase):
    id: int
    menu_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)