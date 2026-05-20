"""Schémas Pydantic pour les résultats de calcul métabolique."""
from pydantic import BaseModel, ConfigDict

from app.models.enums import MainGoal


class MacrosResponse(BaseModel):
    """Répartition des macronutriments calculée pour un objectif donné."""

    model_config = ConfigDict(frozen=True)

    goal: MainGoal
    tdee_kcal: int
    proteins_g: int
    carbs_g: int
    fats_g: int
    proteins_kcal: int
    carbs_kcal: int
    fats_kcal: int


class CalculationResponse(BaseModel):
    """Résultat complet du calcul métabolique : IMC, MB, TDEE, macros, poids idéal."""

    model_config = ConfigDict(frozen=True)

    bmi: float
    bmi_category: str
    bmr_kcal: int
    tdee_kcal: int
    pal: float
    ideal_weight_min_kg: float
    ideal_weight_max_kg: float
    macros: MacrosResponse | None