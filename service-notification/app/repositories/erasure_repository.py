"""Repository d'effacement RGPD — purge des données notification d'un user.

Sert l'endpoint interne (art. 17) appelé par service-user. Idempotent.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class ErasureRepository:
    """Purge les notifications et abonnements d'un utilisateur (RGPD art. 17)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def erase_by_user(self, user_id: uuid.UUID | None) -> int:
        """Supprime notifications + abonnements de l'utilisateur.

        Retourne le nombre total de lignes supprimées — ``0`` si ``user_id`` est
        absent ou si rien ne correspond (idempotent).
        """
        if user_id is None:
            return 0

        notif = await self._session.execute(
            delete(Notification).where(Notification.user_id == user_id)
        )
        subs = await self._session.execute(
            delete(Subscription).where(Subscription.user_id == user_id)
        )
        await self._session.commit()
        deleted = (notif.rowcount or 0) + (subs.rowcount or 0)
        logger.info(
            "Effacement RGPD service-notification : %d ligne(s) supprimée(s)", deleted
        )
        return deleted
