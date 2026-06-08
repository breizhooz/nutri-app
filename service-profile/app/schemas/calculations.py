"""Schémas Pydantic pour les résultats de calcul métabolique."""

from pydantic import BaseModel, ConfigDict

from app.models.enums import MainGoal


class MacrosResponse(BaseModel):
    """Répartition des macronutriments calculée pour un objectif donné.

    ``tdee_kcal`` est la base énergétique sur laquelle la répartition est faite,
    c.-à-d. la **cible** calorique (TDEE ajusté du déficit/surplus de l'objectif),
    et non la maintenance brute. Les ``*_kcal`` somment donc vers cette cible.
    """

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
    # Cible énergétique = TDEE ajusté du déficit/surplus de l'objectif (plancher
    # BMR+100). None si l'objectif nutritionnel n'est pas renseigné.
    target_calories_kcal: int | None = None
    # Ajustement appliqué au TDEE, en % signé (-20 = déficit, +12 = surplus, 0).
    energy_adjustment_pct: int = 0
    # Explication textuelle déterministe (i18n) de l'objectif calculé.
    explanation: str | None = None
