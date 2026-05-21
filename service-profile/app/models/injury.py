"""Modèle Injury — blessure actuelle ou antérieure."""
import logging
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class Injury(Base, SlugMixin, TimestampMixin):
    """Blessure déclarée par l'utilisateur — oriente les recommandations d'exercice."""

    __tablename__ = "injuries"

    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    body_part: Mapped[str] = mapped_column(String(100), nullable=False)
    injury_type: Mapped[str] = mapped_column(String(200), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_chronic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    diagnosed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)