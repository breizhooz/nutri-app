"""Schéma agrégé inter-service : résumé nutritionnel complet d'un utilisateur."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.calculations import CalculationResponse
from app.schemas.medical import (
    FoodAllergyResponse,
    MedicalConditionResponse,
    MedicationResponse,
)
from app.schemas.preferences import (
    ExcludedFoodResponse,
    NutritionPreferencesResponse,
)
from app.schemas.profile import ProfileResponse


class NutritionSummaryResponse(BaseModel):
    """Vue agrégée des informations nutritionnelles d'un utilisateur.

    Destinée aux appels inter-service (service-recipe) : regroupe en une seule
    réponse le profil anthropométrique, le calcul métabolique (BMR/TDEE/macros),
    les préférences nutritionnelles et les contraintes médicales pertinentes.

    Les sections optionnelles valent None (calcul indisponible si données
    anthropométriques incomplètes ; préférences si non renseignées) ; les
    collections valent une liste vide.
    """

    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    profile: ProfileResponse
    calculation: CalculationResponse | None
    nutrition_preferences: NutritionPreferencesResponse | None
    allergies: list[FoodAllergyResponse]
    excluded_foods: list[ExcludedFoodResponse]
    medical_conditions: list[MedicalConditionResponse]
    metabolic_medications: list[MedicationResponse]
