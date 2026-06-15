"""Repository d'effacement RGPD (art. 17) — purge du coffre chiffré d'un compte.

Depuis la bascule E2E zero-knowledge, service-profile ne détient plus de données
de santé en clair : le seul stockage personnel est la table opaque
``encrypted_blobs`` (ciphertext chiffré côté client), adressée par
``account_id``. L'effacement supprime donc tous les blobs des comptes ciblés.
Idempotent. (Le matériel de clés vit dans service-user et est purgé là-bas.)
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encrypted_blob import EncryptedBlob

logger = logging.getLogger(__name__)


class ErasureRepository:
    """Purge les blobs chiffrés d'un ou plusieurs comptes (RGPD art. 17)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def erase_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> int:
        """Supprime tous les blobs chiffrés des comptes ciblés.

        Les blobs sont adressés par ``account_id`` uniquement (aucune notion de
        ``user_id`` côté coffre). Retourne le nombre de blobs effacés — ``0`` si
        rien ne correspond (idempotent).
        """
        if not account_ids:
            return 0

        result = await self._session.execute(
            delete(EncryptedBlob).where(EncryptedBlob.account_id.in_(account_ids))
        )
        await self._session.commit()
        deleted = result.rowcount or 0
        logger.info(
            "Effacement RGPD service-profile : %d blob(s) chiffré(s) supprimé(s)",
            deleted,
        )
        return deleted
