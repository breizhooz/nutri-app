"""Service d'agrégation des informations nutritionnelles d'un utilisateur.

Assemble en une seule vue les données dispersées dans plusieurs tables
(profil, préférences, médical) + le calcul métabolique, pour les exposer
aux autres microservices via un unique appel HTTP.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.medical_repository import MedicalRepository
from app.repositories.preferences_repository import PreferencesRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.medical import (
    FoodAllergyResponse,
    MedicalConditionResponse,
    MedicationResponse,
)
from app.schemas.nutrition_summary import NutritionSummaryResponse
from app.schemas.preferences import (
    ExcludedFoodResponse,
    NutritionPreferencesResponse,
)
from app.schemas.profile import ProfileResponse
from app.services.calculation_service import CalculationService

logger = logging.getLogger(__name__)


class NutritionSummaryService:
    """Construit le résumé nutritionnel complet d'un utilisateur."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le service avec une session (lecture seule ici)."""
        self._profile_repo = ProfileRepository(session)
        self._pref_repo = PreferencesRepository(session)
        self._medical_repo = MedicalRepository(session)

    async def get_summary(
        self, user_id: uuid.UUID, locale: str = "fr"
    ) -> NutritionSummaryResponse | None:
        """Retourne le résumé nutritionnel, ou None si le profil n'existe pas.

        Le calcul métabolique est best-effort : il vaut None si les données
        anthropométriques sont incomplètes (sans faire échouer l'appel).
        """
        profile = await self._profile_repo.get_by_user_id(user_id)
        if not profile:
            return None

        lifestyle = await self._pref_repo.get_lifestyle(profile.id)
        sports = await self._pref_repo.get_sports(profile.id)
        nutrition = await self._pref_repo.get_nutrition(profile.id)
        excluded = await self._pref_repo.list_excluded_foods(profile.id)
        allergies = await self._medical_repo.list_allergies(profile.id)
        conditions = await self._medical_repo.list_conditions(profile.id)
        medications = await self._medical_repo.list_medications(profile.id)

        try:
            calculation = CalculationService().calculate(
                profile, lifestyle, sports, nutrition, locale
            )
        except ValueError:
            logger.info(
                "Calcul métabolique indisponible (données incomplètes) pour user_id=%s",
                user_id,
            )
            calculation = None

        return NutritionSummaryResponse(
            user_id=user_id,
            profile=ProfileResponse.model_validate(profile),
            calculation=calculation,
            nutrition_preferences=(
                NutritionPreferencesResponse.model_validate(nutrition)
                if nutrition
                else None
            ),
            allergies=[FoodAllergyResponse.model_validate(a) for a in allergies],
            excluded_foods=[ExcludedFoodResponse.model_validate(e) for e in excluded],
            medical_conditions=[
                MedicalConditionResponse.model_validate(c) for c in conditions
            ],
            metabolic_medications=[
                MedicationResponse.model_validate(m)
                for m in medications
                if m.impacts_metabolism
            ],
        )
