"""Modèle Medication — traitement médicamenteux en cours."""

import logging
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from nutri_shared.db.encrypted import EncryptedText

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class Medication(Base, SlugMixin, TimestampMixin):
    """Médicament suivi par l'utilisateur, notamment si impact sur le poids ou la performance."""

    __tablename__ = "medications"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    medication_name: Mapped[str] = mapped_column(String(200), nullable=False)
    impacts_metabolism: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notes: Mapped[str | None] = mapped_column(
        EncryptedText("PROFILE_FIELD_ENCRYPTION_KEY"), nullable=True
    )
