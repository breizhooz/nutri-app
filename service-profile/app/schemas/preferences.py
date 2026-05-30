"""Schémas Pydantic pour les endpoints de personnalisation."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import (
    ActivityLevel,
    AlcoholFrequency,
    Chronotype,
    CookingFor,
    CookingLevel,
    CookingTime,
    DietType,
    MainGoal,
    PracticeLevel,
    StressLevel,
)


class SportsProfileCreate(BaseModel):
    """Données d'entrée pour le profil sportif."""

    model_config = ConfigDict(frozen=True)

    sports: list[str]
    practice_level: PracticeLevel
    sessions_per_week: int
    avg_session_duration_min: int
    avg_intensity_rpe: int
    resting_heart_rate_bpm: int | None = None

    @field_validator("avg_intensity_rpe")
    @classmethod
    def rpe_range(cls, v: int) -> int:
        """Valide que le RPE est compris entre 1 et 10."""
        if not 1 <= v <= 10:
            raise ValueError("Le RPE doit être compris entre 1 et 10")
        return v


class SportsProfileResponse(BaseModel):
    """Réponse HTTP du profil sportif."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    sports: list[str]
    practice_level: PracticeLevel
    sessions_per_week: int
    avg_session_duration_min: int
    avg_intensity_rpe: int
    resting_heart_rate_bpm: int | None
    updated_at: datetime


class PerformanceMetricCreate(BaseModel):
    """Données d'entrée pour une métrique de performance."""

    model_config = ConfigDict(frozen=True)

    measured_at: date
    vo2max: float | None = None
    vma_kmh: float | None = None
    ftp_watts: int | None = None
    one_rm_squat_kg: float | None = None
    one_rm_bench_press_kg: float | None = None
    one_rm_deadlift_kg: float | None = None
    one_rm_overhead_press_kg: float | None = None


class PerformanceMetricResponse(BaseModel):
    """Réponse HTTP d'une métrique de performance."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    measured_at: date
    vo2max: float | None
    vma_kmh: float | None
    ftp_watts: int | None
    one_rm_squat_kg: float | None
    one_rm_bench_press_kg: float | None
    one_rm_deadlift_kg: float | None
    one_rm_overhead_press_kg: float | None
    created_at: datetime


class LifestyleProfileCreate(BaseModel):
    """Données d'entrée pour le profil de mode de vie."""

    model_config = ConfigDict(frozen=True)

    profession_activity_level: ActivityLevel | None = None
    stress_level: StressLevel | None = None
    sleep_hours: float | None = None
    chronotype: Chronotype | None = None
    alcohol_frequency: AlcoholFrequency | None = None
    is_smoker: bool = False
    sedentary_hours_per_day: float | None = None


class LifestyleProfileResponse(BaseModel):
    """Réponse HTTP du profil de mode de vie."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    profession_activity_level: ActivityLevel | None
    stress_level: StressLevel | None
    sleep_hours: float | None
    chronotype: Chronotype | None
    alcohol_frequency: AlcoholFrequency | None
    is_smoker: bool
    sedentary_hours_per_day: float | None
    updated_at: datetime


class NutritionPreferencesCreate(BaseModel):
    """Données d'entrée pour les préférences nutritionnelles."""

    model_config = ConfigDict(frozen=True)

    diet_type: DietType
    diet_type_other: str | None = None
    main_goal: MainGoal
    meals_per_day: int | None = None
    snacks_per_day: int | None = None
    practices_if: bool = False
    fasting_window_hours: int | None = None
    cooking_level: CookingLevel | None = None
    cooking_time_available: CookingTime | None = None
    cooking_for: CookingFor | None = None
    hydration_target_ml: int | None = None
    supplements: list[str] = []
    budget_per_day_eur: float | None = None
    medical_contraindications: str | None = None
    excluded_foods: list[str] = []
    rules_aggressiveness: float = 1.0
    rules_variety_pct: float = 0.10
    rules_override_calories: int | None = None
    rules_override_proteines: int | None = None


class NutritionPreferencesResponse(BaseModel):
    """Réponse HTTP des préférences nutritionnelles."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    diet_type: DietType
    diet_type_other: str | None
    main_goal: MainGoal
    meals_per_day: int | None
    snacks_per_day: int | None
    practices_if: bool
    fasting_window_hours: int | None
    cooking_level: CookingLevel | None
    cooking_time_available: CookingTime | None
    cooking_for: CookingFor | None
    hydration_target_ml: int | None
    supplements: list[str]
    budget_per_day_eur: float | None
    medical_contraindications: str | None
    excluded_foods: list[str]
    rules_aggressiveness: float
    rules_variety_pct: float
    rules_override_calories: int | None
    rules_override_proteines: int | None
    updated_at: datetime


class ExcludedFoodCreate(BaseModel):
    """Données d'entrée pour exclure un aliment."""

    model_config = ConfigDict(frozen=True)

    food_name: str
    food_id: uuid.UUID | None = None
    reason: str | None = None


class ExcludedFoodResponse(BaseModel):
    """Réponse HTTP d'un aliment exclu."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: uuid.UUID
    slug: str
    profile_id: uuid.UUID
    food_name: str
    food_id: uuid.UUID | None
    reason: str | None
    created_at: datetime
