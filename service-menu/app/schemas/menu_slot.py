from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from app.models.enums import DayOfWeek, MealType


class MenuSlotBase(BaseModel):
    day_of_week: DayOfWeek = DayOfWeek.MONDAY
    meal_type: MealType = MealType.BREAKFAST
    recipe_id: int


class MenuSlotCreate(MenuSlotBase):
    # None => hérite du nb_persons du menu à la création
    nb_persons: Optional[int] = Field(default=None, ge=1)


class MenuSlotUpdate(BaseModel):
    day_of_week: Optional[DayOfWeek] = None
    meal_type: Optional[MealType] = None
    recipe_id: Optional[int] = None
    nb_persons: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(from_attributes=True)


class MenuSlotResponse(MenuSlotBase):
    id: int
    menu_id: int
    nb_persons: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
