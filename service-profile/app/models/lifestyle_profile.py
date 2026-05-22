"""Modèle ORM pour le profil de style de vie."""

import logging
import uuid

from sqlalchemy import Boolean, Float, String, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, UpdatedAtMixin
from app.models.enums.enums import (
    ActivityLevel,
    AlcoholFrequency,
    Chronotype,
    StressLevel,
)

logger = logging.getLogger(__name__)


class LifestyleProfile(Base, SlugMixin, UpdatedAtMixin):
    """Profil de style de vie lié à un profil utilisateur."""

    __tablename__ = "lifestyle_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    profession_activity_level: Mapped[ActivityLevel | None] = mapped_column(
        String(32), nullable=True
    )
    stress_level: Mapped[StressLevel | None] = mapped_column(String(32), nullable=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    chronotype: Mapped[Chronotype | None] = mapped_column(String(32), nullable=True)
    alcohol_frequency: Mapped[AlcoholFrequency | None] = mapped_column(
        String(32), nullable=True
    )
    is_smoker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sedentary_hours_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
