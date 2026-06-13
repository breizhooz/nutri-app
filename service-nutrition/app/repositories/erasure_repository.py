"""Repository d'effacement RGPD — purge des macro_errors d'un compte.

Sert l'endpoint interne (art. 17) appelé par service-user. Idempotent.

Note : ``nutrition_items`` (source utilisateur) sont des données de référence
(valeurs nutritionnelles d'un aliment) et ne sont pas purgées.
"""

import logging
import uuid

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro_error import MacroError

logger = logging.getLogger(__name__)


class ErasureRepository:
    """Purge les macro_errors d'un compte / utilisateur (RGPD art. 17)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def erase_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> int:
        """Supprime les macro_errors ciblés par ``account_id`` ou ``user_id``.

        Retourne le nombre de lignes supprimées — ``0`` si rien ne correspond
        (idempotent).
        """
        filters = []
        if account_ids:
            filters.append(MacroError.account_id.in_(account_ids))
        if user_id is not None:
            filters.append(MacroError.user_id == user_id)
        if not filters:
            return 0

        result = await self._session.execute(delete(MacroError).where(or_(*filters)))
        await self._session.commit()
        deleted = result.rowcount or 0
        logger.info(
            "Effacement RGPD service-nutrition : %d macro_error(s) supprimée(s)",
            deleted,
        )
        return deleted
