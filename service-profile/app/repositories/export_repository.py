"""Repository d'export RGPD (art. 20, portabilité) — coffre chiffré d'un compte.

Depuis la bascule E2E zero-knowledge, service-profile ne détient que des blobs
OPAQUES (ciphertext chiffré côté client) ; il ne peut PAS produire un export en
clair. L'export retourne donc les blobs tels quels (ciphertext base64 +
enveloppe d'adressage) : c'est la portabilité de la donnée *chiffrée*, qui,
combinée au matériel de clés (service-user), permet à l'utilisateur de la
déchiffrer hors ligne. Lecture seule, miroir de :class:`ErasureRepository`.
"""

import base64
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encrypted_blob import EncryptedBlob

logger = logging.getLogger(__name__)


class ExportRepository:
    """Assemble l'export du coffre chiffré d'un compte (RGPD art. 20)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def export_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Retourne les blobs chiffrés (opaques) des comptes ciblés.

        ``{"encrypted_blobs": [...]}`` (liste vide si rien ne correspond). Le
        ciphertext est encodé en base64 ; le serveur n'en connaît jamais le clair.
        """
        if not account_ids:
            return {"encrypted_blobs": []}

        rows = await self._session.execute(
            select(EncryptedBlob).where(EncryptedBlob.account_id.in_(account_ids))
        )
        blobs = [
            {
                "collection": b.collection,
                "ref_key": b.ref_key,
                "content_version": b.content_version,
                "ciphertext": base64.b64encode(b.ciphertext).decode(),
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            }
            for b in rows.scalars()
        ]
        logger.info("Export RGPD service-profile : %d blob(s) chiffré(s)", len(blobs))
        return {"encrypted_blobs": blobs}
