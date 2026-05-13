from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Any
from datetime import date, datetime

from app.models.enums import Allergen
from app.schemas.menu_slot import MenuSlotCreate, MenuSlotResponse


class WeeklyMenuBase(BaseModel):
    slug: Optional[str] = Field(default=None, max_length=350)
    user_id: Optional[str] = Field(default=None, max_length=36)
    nb_persons: int = Field(default=1, ge=1)
    caloric_target: Optional[int] = Field(default=None, ge=0)
    start_date: date
    exclusions: list[Allergen] = []
    free_tags: dict[str, Any] = {}
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class WeeklyMenuCreate(WeeklyMenuBase):
    slots: list[MenuSlotCreate] = []

    @field_validator("slug")
    @classmethod
    def slug_no_spaces(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and " " in v:
            raise ValueError("Le slug ne doit pas contenir d'espaces.")
        return v


class WeeklyMenuUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, max_length=350)
    nb_persons: Optional[int] = Field(default=None, ge=1)
    caloric_target: Optional[int] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    exclusions: Optional[list[Allergen]] = None
    free_tags: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    slots: Optional[list[MenuSlotCreate]] = None

    model_config = ConfigDict(from_attributes=True)


class WeeklyMenuResponse(WeeklyMenuBase):
    id: int
    created_at: datetime
    updated_at: datetime
    slots: list[MenuSlotResponse]

    model_config = ConfigDict(from_attributes=True)