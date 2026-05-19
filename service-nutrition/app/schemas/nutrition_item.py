import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums.enums import NutritionSource


class NutritionItemResponse(BaseModel):
    id: uuid.UUID
    slug: str
    nom_fr: str
    nom_en: str | None
    calories: float | None
    proteines: float | None
    glucides: float | None
    lipides: float | None
    fibres: float | None
    source: NutritionSource
    ciqual_id: int | None
    off_id: str | None
    off_enriched: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NutritionItemUpdate(BaseModel):
    nom_fr: str | None = None
    nom_en: str | None = None
    calories: float | None = Field(default=None, ge=0)
    proteines: float | None = Field(default=None, ge=0)
    glucides: float | None = Field(default=None, ge=0)
    lipides: float | None = Field(default=None, ge=0)
    fibres: float | None = Field(default=None, ge=0)