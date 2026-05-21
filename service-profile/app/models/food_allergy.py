"""Modèle FoodAllergy — intolérance ou allergie alimentaire."""
import logging
import uuid
from datetime import datetime

from sqlalchemy import Text, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin
from app.models.enums import AllergySeverity

logger = logging.getLogger(__name__)


class FoodAllergy(Base, SlugMixin, TimestampMixin):
    """Allergie ou intolérance alimentaire — exclut automatiquement les recettes concernées."""

    __tablename__ = "food_allergies"

    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    allergen: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[AllergySeverity] = mapped_column(
        SQLEnum(AllergySeverity, native_enum=False, length=15), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)