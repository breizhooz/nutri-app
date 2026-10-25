"""Repository d'effacement RGPD (art. 17) — purge du profil d'un compte.

Le seul stockage personnel de service-profile est la table ``nutrition_profiles``
(préférences, exclusions, cibles), adressée par ``account_id``. Idempotent.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_profile import NutritionProfile

logger = logging.getLogger(__name__)


class ErasureRepository:
    """Purge le profil d'un ou plusieurs comptes (RGPD art. 17)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def erase_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> int:
        """Supprime les profils des comptes ciblés ; ``0`` si rien (idempotent).

        Le profil est adressé par ``account_id`` uniquement (``user_id`` ignoré).
        """
        if not account_ids:
            return 0

        result = await self._session.execute(
            delete(NutritionProfile).where(NutritionProfile.account_id.in_(account_ids))
        )
        await self._session.commit()
        deleted = result.rowcount or 0
        logger.info(
            "Effacement RGPD service-profile : %d profil(s) supprimé(s)", deleted
        )
        return deleted
