"""Schémas du profil nutritionnel (sans donnée de santé) et de son résumé
inter-service (consommé par service-menu et service-recipe)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CookingFor, CookingLevel, CookingTime, DietType, MainGoal

_MAX_EXCLUDED_FOODS = 100
_MAX_FOOD_NAME = 100
# Colonnes NOT NULL du modèle : modifiables, jamais remises à null.
_NOT_NULLABLE = frozenset(
    {
        "main_goal",
        "diet_type",
        "practices_if",
        "excluded_foods",
        "nutrition_rules_enabled",
        "rules_variety_pct",
    }
)


class ProfileUpdate(BaseModel):
    """Mise à jour partielle : seuls les champs envoyés sont modifiés."""

    model_config = ConfigDict(extra="forbid")

    main_goal: MainGoal | None = None
    diet_type: DietType | None = None
    diet_type_other: str | None = Field(default=None, max_length=100)
    meals_per_day: int | None = Field(default=None, ge=1, le=10)
    snacks_per_day: int | None = Field(default=None, ge=0, le=10)
    practices_if: bool | None = None
    fasting_window_hours: int | None = Field(default=None, ge=1, le=23)
    cooking_level: CookingLevel | None = None
    cooking_time_available: CookingTime | None = None
    cooking_for: CookingFor | None = None
    budget_per_day_eur: Decimal | None = Field(default=None, ge=0, le=10000)
    excluded_foods: list[str] | None = Field(
        default=None, max_length=_MAX_EXCLUDED_FOODS
    )
    nutrition_rules_enabled: bool | None = None
    rules_variety_pct: float | None = Field(default=None, ge=0.0, le=0.5)
    rules_override_calories: int | None = Field(default=None, ge=0, le=10000)
    rules_override_proteines: int | None = Field(default=None, ge=0, le=1000)
    target_calories_kcal: int | None = Field(default=None, ge=0, le=10000)
    target_proteins_g: int | None = Field(default=None, ge=0, le=1000)
    target_carbs_g: int | None = Field(default=None, ge=0, le=2000)
    target_fats_g: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> "ProfileUpdate":
        """Champs obligatoires : absents = inchangés, mais jamais remis à null."""
        nulled = sorted(
            name
            for name in _NOT_NULLABLE & self.model_fields_set
            if getattr(self, name) is None
        )
        if nulled:
            raise ValueError(f"ne peuvent pas être null : {', '.join(nulled)}")
        return self

    @field_validator("excluded_foods")
    @classmethod
    def _clean_foods(cls, foods: list[str] | None) -> list[str] | None:
        """Espaces retirés, vides écartés, doublons (casse ignorée) fusionnés."""
        if foods is None:
            return None
        seen: dict[str, str] = {}
        for food in foods:
            name = " ".join(food.split())[:_MAX_FOOD_NAME]
            if name:
                seen.setdefault(name.casefold(), name)
        return list(seen.values())


class ProfileRead(BaseModel):
    """Profil tel que renvoyé au front."""

    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    main_goal: MainGoal
    diet_type: DietType
    diet_type_other: str | None
    meals_per_day: int | None
    snacks_per_day: int | None
    practices_if: bool
    fasting_window_hours: int | None
    cooking_level: CookingLevel | None
    cooking_time_available: CookingTime | None
    cooking_for: CookingFor | None
    budget_per_day_eur: Decimal | None
    excluded_foods: list[str]
    nutrition_rules_enabled: bool
    rules_variety_pct: float
    rules_override_calories: int | None
    rules_override_proteines: int | None
    target_calories_kcal: int | None
    target_proteins_g: int | None
    target_carbs_g: int | None
    target_fats_g: int | None
    updated_at: datetime


class TargetsSummary(BaseModel):
    """Cibles journalières (kcal + macros en grammes, convention française)."""

    calories: int
    proteines: int | None
    glucides: int | None
    lipides: int | None


class RulesSummary(BaseModel):
    """Curseurs de la recherche personnalisée."""

    enabled: bool
    variety_pct: float
    override_calories: int | None
    override_proteines: int | None


class NutritionSummary(BaseModel):
    """Résumé inter-service : de quoi filtrer menus et recherche, rien de plus."""

    account_id: uuid.UUID
    main_goal: str
    diet_type: str
    excluded_foods: list[str]
    targets: TargetsSummary | None
    rules: RulesSummary
