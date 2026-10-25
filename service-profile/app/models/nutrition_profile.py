"""Profil nutritionnel d'un compte : préférences et cibles, sans donnée de santé.

Allègement RGPD (2026-10-24) — fin du coffre chiffré côté client :
  • plus aucune donnée médicale (pathologies, médicaments, blessures, allergies,
    composition corporelle, mensurations, marqueurs de mode de vie) ;
  • les données corporelles (poids, taille, âge, sexe) et le volume d'activité
    restent sur l'appareil, qui calcule les cibles et ne transmet que le résultat
    (``target_*``) ; un coach peut aussi les fixer (docs/coaching_model.md §10) ;
  • les allergies sont fondues dans ``excluded_foods`` : de simples noms d'aliments,
    sans gravité ni motif.

Un profil par compte (``account_id``, frontière multicomptes).
"""

import uuid
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Float, Integer, Numeric, SmallInteger, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import TimestampMixin, UpdatedAtMixin
from app.models.enums import CookingFor, CookingLevel, CookingTime, DietType, MainGoal


class NutritionProfile(Base, TimestampMixin, UpdatedAtMixin):
    """Préférences alimentaires, objectif et cibles nutritionnelles d'un compte."""

    __tablename__ = "nutrition_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )

    main_goal: Mapped[MainGoal] = mapped_column(
        SQLEnum(MainGoal, native_enum=False, length=25),
        nullable=False,
        default=MainGoal.MAINTENANCE,
    )
    diet_type: Mapped[DietType] = mapped_column(
        SQLEnum(DietType, native_enum=False, length=15),
        nullable=False,
        default=DietType.OMNIVORE,
    )
    diet_type_other: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    budget_per_day_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2), nullable=True
    )
    # Noms d'aliments à écarter (ex-allergies comprises), sans motif.
    excluded_foods: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Recherche personnalisée (moteur de cibles) : activation + curseurs UI.
    nutrition_rules_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    rules_variety_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.10
    )
    rules_override_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_override_proteines: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cibles journalières calculées sur l'appareil (ou fixées par un coach).
    target_calories_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_proteins_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_carbs_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_fats_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
