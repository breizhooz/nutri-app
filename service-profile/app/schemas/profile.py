"""Schémas Pydantic pour les endpoints Profile."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BiologicalSex


class ProfileCreate(BaseModel):
    """Données d'entrée pour la création d'un profil."""

    model_config = ConfigDict(frozen=True)

    date_of_birth: date | None = None
    biological_sex: BiologicalSex | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    target_weight_kg: float | None = None


class ProfileUpdate(BaseModel):
    """Données d'entrée pour la mise à jour partielle d'un profil."""

    model_config = ConfigDict(frozen=True)

    date_of_birth: date | None = None
    biological_sex: BiologicalSex | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    target_weight_kg: float | None = None


class ProfileResponse(BaseModel):
    """Réponse HTTP d'un profil — jamais d'objet ORM directement."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    date_of_birth: date | None
    biological_sex: BiologicalSex | None
    height_cm: float | None
    weight_kg: float | None
    target_weight_kg: float | None
    created_at: datetime
    updated_at: datetime
