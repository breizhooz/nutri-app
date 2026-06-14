"""Repository d'export RGPD (art. 20, portabilité) — dossier profil.

Sert l'endpoint interne d'export : rassemble le dossier profil d'un compte et
toutes ses sous-ressources de santé sous forme de dicts JSON-sérialisables.
Lecture seule, miroir de ``ErasureRepository``.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import or_, select
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

# (clé d'export, modèle) des sous-ressources rattachées via ``profile_id``.
_CHILD_MODELS: tuple[tuple[str, Any], ...] = (
    ("body_composition_snapshots", BodyCompositionSnapshot),
    ("body_measurements_snapshots", BodyMeasurementsSnapshot),
    ("excluded_foods", ExcludedFood),
    ("food_allergies", FoodAllergy),
    ("injuries", Injury),
    ("lifestyle_profiles", LifestyleProfile),
    ("medical_conditions", MedicalCondition),
    ("medications", Medication),
    ("nutrition_preferences", NutritionPreferences),
    ("performance_metrics", PerformanceMetric),
    ("sports_profiles", SportsProfile),
)


def _json_value(value: Any) -> Any:
    """Normalise une valeur de colonne pour la sérialisation JSON."""
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value) if isinstance(value, uuid.UUID) else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def row_to_dict(obj: Any) -> dict[str, Any]:
    """Sérialise une ligne ORM en dict JSON-able (colonnes uniquement)."""
    return {
        col.name: _json_value(getattr(obj, col.name)) for col in obj.__table__.columns
    }


class ExportRepository:
    """Assemble l'export d'un dossier profil (RGPD art. 20)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def export_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Retourne le(s) dossier(s) profil ciblé(s) + sous-ressources.

        Cible les profils par ``account_id`` OU ``user_id`` (clé legacy).
        Retourne ``{"profiles": [...]}`` (liste vide si rien ne correspond).
        """
        filters = []
        if account_ids:
            filters.append(Profile.account_id.in_(account_ids))
        if user_id is not None:
            filters.append(Profile.user_id == user_id)
        if not filters:
            return {"profiles": []}

        rows = await self._session.execute(select(Profile).where(or_(*filters)))
        profiles = list(rows.scalars())

        export: list[dict[str, Any]] = []
        for profile in profiles:
            entry = row_to_dict(profile)
            for key, model in _CHILD_MODELS:
                child_rows = await self._session.execute(
                    select(model).where(model.profile_id == profile.id)
                )
                entry[key] = [row_to_dict(c) for c in child_rows.scalars()]
            export.append(entry)

        logger.info("Export RGPD service-profile : %d profil(s)", len(export))
        return {"profiles": export}
