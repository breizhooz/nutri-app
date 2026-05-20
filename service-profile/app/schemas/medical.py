"""Schémas Pydantic pour les endpoints médicaux."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AllergySeverity, MedicalCategory


class InjuryCreate(BaseModel):
    """Données d'entrée pour déclarer une blessure."""

    model_config = ConfigDict(frozen=True)

    body_part: str
    injury_type: str
    is_current: bool = True
    is_chronic: bool = False
    diagnosed_at: date | None = None
    notes: str | None = None


class InjuryResponse(BaseModel):
    """Réponse HTTP d'une blessure."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    body_part: str
    injury_type: str
    is_current: bool
    is_chronic: bool
    diagnosed_at: date | None
    notes: str | None
    created_at: datetime


class MedicalConditionCreate(BaseModel):
    """Données d'entrée pour déclarer une pathologie."""

    model_config = ConfigDict(frozen=True)

    category: MedicalCategory
    condition_name: str
    is_current: bool = True
    notes: str | None = None


class MedicalConditionResponse(BaseModel):
    """Réponse HTTP d'une pathologie."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    category: MedicalCategory
    condition_name: str
    is_current: bool
    notes: str | None
    created_at: datetime


class FoodAllergyCreate(BaseModel):
    """Données d'entrée pour déclarer une allergie ou intolérance."""

    model_config = ConfigDict(frozen=True)

    allergen: str
    severity: AllergySeverity
    notes: str | None = None


class FoodAllergyResponse(BaseModel):
    """Réponse HTTP d'une allergie."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    allergen: str
    severity: AllergySeverity
    notes: str | None
    created_at: datetime


class MedicationCreate(BaseModel):
    """Données d'entrée pour déclarer un traitement médicamenteux."""

    model_config = ConfigDict(frozen=True)

    medication_name: str
    impacts_metabolism: bool = False
    notes: str | None = None


class MedicationResponse(BaseModel):
    """Réponse HTTP d'un traitement."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    medication_name: str
    impacts_metabolism: bool
    notes: str | None
    created_at: datetime