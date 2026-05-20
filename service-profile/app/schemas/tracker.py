"""Schémas Pydantic pour les endpoints de suivi corporel."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BodyCompositionCreate(BaseModel):
    """Données d'entrée pour un snapshot de composition corporelle."""

    model_config = ConfigDict(frozen=True)

    measured_at: date
    body_fat_percentage: float | None = None
    lean_mass_kg: float | None = None
    bone_mass_kg: float | None = None
    water_percentage: float | None = None


class BodyCompositionResponse(BaseModel):
    """Réponse HTTP d'un snapshot de composition."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    measured_at: date
    body_fat_percentage: float | None
    lean_mass_kg: float | None
    bone_mass_kg: float | None
    water_percentage: float | None
    created_at: datetime


class BodyMeasurementsCreate(BaseModel):
    """Données d'entrée pour un snapshot de mensurations."""

    model_config = ConfigDict(frozen=True)

    measured_at: date
    waist_cm: float | None = None
    hips_cm: float | None = None
    chest_cm: float | None = None
    shoulders_cm: float | None = None
    left_arm_cm: float | None = None
    right_arm_cm: float | None = None
    left_thigh_cm: float | None = None
    right_thigh_cm: float | None = None


class BodyMeasurementsResponse(BaseModel):
    """Réponse HTTP d'un snapshot de mensurations."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    measured_at: date
    waist_cm: float | None
    hips_cm: float | None
    chest_cm: float | None
    shoulders_cm: float | None
    left_arm_cm: float | None
    right_arm_cm: float | None
    left_thigh_cm: float | None
    right_thigh_cm: float | None
    created_at: datetime