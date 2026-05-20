"""Modèle ExcludedFood — aliment banni des suggestions pour un utilisateur."""
import logging
import uuid
from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class ExcludedFood(Base, SlugMixin, TimestampMixin):
    """Aliment explicitement exclu des suggestions — aversion, intolérance ou choix personnel."""

    __tablename__ = "excluded_foods"

    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    food_name: Mapped[str] = mapped_column(String(200), nullable=False)
    food_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)