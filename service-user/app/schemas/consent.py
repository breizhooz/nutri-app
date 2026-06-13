"""Schémas de consentement RGPD (art. 9, Phase 2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsentRecordIn(BaseModel):
    """Octroi ou retrait d'un consentement par l'utilisateur connecté."""

    consent_type: str = Field(..., max_length=32, examples=["health_data"])
    version: str = Field(..., max_length=16, examples=["v1"])
    granted: bool = True


class ConsentOut(BaseModel):
    """État courant d'un type de consentement (dernière trace en date)."""

    model_config = ConfigDict(from_attributes=True)

    consent_type: str
    version: str
    granted: bool
    created_at: datetime
