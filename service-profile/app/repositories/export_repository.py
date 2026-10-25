"""Repository d'export RGPD (art. 20, portabilité) — profil d'un compte.

Lecture seule, miroir de :class:`ErasureRepository`.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_profile import NutritionProfile
from app.schemas.profile import ProfileRead

logger = logging.getLogger(__name__)


class ExportRepository:
    """Assemble l'export du profil d'un compte (RGPD art. 20)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def export_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """``{"nutrition_profiles": [...]}`` (liste vide si rien ne correspond)."""
        if not account_ids:
            return {"nutrition_profiles": []}

        rows = await self._session.execute(
            select(NutritionProfile).where(NutritionProfile.account_id.in_(account_ids))
        )
        profiles = [
            ProfileRead.model_validate(p).model_dump(mode="json")
            for p in rows.scalars()
        ]
        logger.info("Export RGPD service-profile : %d profil(s)", len(profiles))
        return {"nutrition_profiles": profiles}
