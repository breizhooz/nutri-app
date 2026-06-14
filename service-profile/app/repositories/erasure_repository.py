"""Repository d'effacement RGPD — purge cross-table d'un dossier profil.

Sert l'endpoint interne (art. 17, droit à l'effacement) : supprime le profil
d'un compte et toutes ses sous-ressources de santé. Idempotent.
"""

import logging
import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_composition_snapshot import BodyCompositionSnapshot
from app.models.body_measurements_snapshot import BodyMeasurementsSnapshot
from app.models.excluded_food import ExcludedFood
from app.models.food_allergy import FoodAllergy
from app.models.injury import Injury
from app.models.lifestyle_profile import LifestyleProfile
from app.models.medical_condition import MedicalCondition
from app.models.medication import Medication
from app.models.nutrition_preferences import NutritionPreferences
from app.models.performance_metric import PerformanceMetric
from app.models.profile import Profile
from app.models.sports_profile import SportsProfile

logger = logging.getLogger(__name__)

# Tables filles rattachées au profil via ``profile_id``. Aucune FK physique :
# suppression explicite (robuste SQLite des tests + Postgres runtime).
_CHILD_MODELS = (
    BodyCompositionSnapshot,
    BodyMeasurementsSnapshot,
    ExcludedFood,
    FoodAllergy,
    Injury,
    LifestyleProfile,
    MedicalCondition,
    Medication,
    NutritionPreferences,
    PerformanceMetric,
    SportsProfile,
)


class ErasureRepository:
    """Purge l'intégralité d'un dossier profil (RGPD art. 17)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def erase_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> int:
        """Supprime le(s) profil(s) ciblé(s) et toutes leurs sous-ressources.

        Cible les profils dont ``account_id`` figure dans ``account_ids`` OU dont
        ``user_id`` correspond (clé legacy). Retourne le nombre de profils
        effacés — ``0`` si rien ne correspond (idempotent).
        """
        filters = []
        if account_ids:
            filters.append(Profile.account_id.in_(account_ids))
        if user_id is not None:
            filters.append(Profile.user_id == user_id)
        if not filters:
            return 0

        rows = await self._session.execute(select(Profile.id).where(or_(*filters)))
        profile_ids = [r[0] for r in rows.all()]
        if not profile_ids:
            return 0

        for model in _CHILD_MODELS:
            await self._session.execute(
                delete(model).where(model.profile_id.in_(profile_ids))
            )
        await self._session.execute(delete(Profile).where(Profile.id.in_(profile_ids)))
        await self._session.commit()
        logger.info(
            "Effacement RGPD service-profile : %d profil(s) supprimé(s)",
            len(profile_ids),
        )
        return len(profile_ids)
