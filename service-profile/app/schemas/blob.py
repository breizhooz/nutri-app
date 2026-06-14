"""Schémas du coffre de blobs chiffrés (E2E). Le ciphertext transite en base64."""

from datetime import datetime

from pydantic import BaseModel, Field


class BlobPutIn(BaseModel):
    """Corps d'un PUT : le ciphertext opaque, encodé base64."""

    ciphertext: str = Field(..., description="Ciphertext opaque encodé en base64.")


class BlobOut(BaseModel):
    """Un blob renvoyé au client (ciphertext base64 + version)."""

    collection: str
    ref_key: str
    content_version: int
    ciphertext: str


class BlobEnvelopeOut(BaseModel):
    """Enveloppe d'un blob (sans ciphertext) — listing pour la synchro multi-appareils."""

    collection: str
    ref_key: str
    content_version: int
    updated_at: datetime
