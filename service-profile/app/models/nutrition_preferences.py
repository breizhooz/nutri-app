"""Modèle NutritionPreferences — préférences alimentaires et objectifs."""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Float, Integer, JSON, Numeric, SmallInteger, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, UpdatedAtMixin
from app.models.enums import CookingFor, CookingLevel, CookingTime, DietType, MainGoal

logger = logging.getLogger(__name__)


class NutritionPreferences(Base, SlugMixin, UpdatedAtMixin):
    """Préférences nutritionnelles — personnalise les plans de repas générés."""

    __tablename__ = "nutrition_preferences"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    diet_type: Mapped[DietType] = mapped_column(
        SQLEnum(DietType, native_enum=False, length=15), nullable=False
    )
    diet_type_other: Mapped[str | None] = mapped_column(String(100), nullable=True)
    main_goal: Mapped[MainGoal] = mapped_column(
        SQLEnum(MainGoal, native_enum=False, length=25), nullable=False
    )
    meals_per_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    snacks_per_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    practices_if: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fasting_window_hours: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    cooking_level: Mapped[CookingLevel | None] = mapped_column(
        SQLEnum(CookingLevel, native_enum=False, length=15), nullable=True
    )
    cooking_time_available: Mapped[CookingTime | None] = mapped_column(
        SQLEnum(CookingTime, native_enum=False, length=15), nullable=True
    )
    cooking_for: Mapped[CookingFor | None] = mapped_column(
        SQLEnum(CookingFor, native_enum=False, length=15), nullable=True
    )
    hydration_target_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplements: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    budget_per_day_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2), nullable=True
    )
    medical_contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded_foods: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    # Réglages d'ajustement des règles (curseurs UI) — défauts persistés.
    rules_aggressiveness: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    rules_variety_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.10, server_default="0.1"
    )
    rules_override_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_override_proteines: Mapped[int | None] = mapped_column(Integer, nullable=True)
