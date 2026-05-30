"""Schémas du résumé nutritionnel récupéré auprès de service-profile.

Miroir tolérant de la réponse de service-profile : les énumérations sont typées
en ``str`` et ``extra="ignore"`` est activé pour rester découplé des évolutions
de schéma côté profile.
"""

import uuid

from pydantic import BaseModel, ConfigDict


class _Loose(BaseModel):
    """Base permissive : ignore les champs inconnus de service-profile."""

    model_config = ConfigDict(extra="ignore")


class MacrosSummary(_Loose):
    """Répartition des macronutriments pour l'objectif de l'utilisateur."""

    goal: str
    tdee_kcal: int
    proteins_g: int
    carbs_g: int
    fats_g: int


class CalculationSummary(_Loose):
    """Résultat du calcul métabolique."""

    bmi: float
    bmi_category: str
    bmr_kcal: int
    tdee_kcal: int
    pal: float
    ideal_weight_min_kg: float
    ideal_weight_max_kg: float
    macros: MacrosSummary | None = None


class ProfileSummary(_Loose):
    """Données anthropométriques de base."""

    biological_sex: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    target_weight_kg: float | None = None
    nutrition_rules_enabled: bool = False


class NutritionPreferencesSummary(_Loose):
    """Préférences nutritionnelles pertinentes pour les recettes."""

    diet_type: str
    diet_type_other: str | None = None
    main_goal: str
    meals_per_day: int | None = None
    snacks_per_day: int | None = None
    practices_if: bool = False
    hydration_target_ml: int | None = None
    supplements: list[str] = []
    excluded_foods: list[str] = []
    medical_contraindications: str | None = None
    rules_aggressiveness: float = 1.0
    rules_variety_pct: float = 0.10
    rules_override_calories: int | None = None
    rules_override_proteines: int | None = None


class AllergySummary(_Loose):
    """Allergène déclaré et sévérité."""

    allergen: str
    severity: str


class ExcludedFoodSummary(_Loose):
    """Aliment explicitement exclu."""

    food_name: str
    reason: str | None = None


class MedicalConditionSummary(_Loose):
    """Pathologie déclarée."""

    category: str
    condition_name: str


class MedicationSummary(_Loose):
    """Traitement impactant le métabolisme."""

    medication_name: str
    impacts_metabolism: bool


class NutritionSummary(_Loose):
    """Vue agrégée des informations nutritionnelles d'un utilisateur."""

    user_id: uuid.UUID
    profile: ProfileSummary | None = None
    calculation: CalculationSummary | None = None
    nutrition_preferences: NutritionPreferencesSummary | None = None
    allergies: list[AllergySummary] = []
    excluded_foods: list[ExcludedFoodSummary] = []
    medical_conditions: list[MedicalConditionSummary] = []
    metabolic_medications: list[MedicationSummary] = []
