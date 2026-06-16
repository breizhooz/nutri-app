"""Effacement RGPD (art. 17) — purge des menus d'un compte.

Sert l'endpoint interne appelé par service-user. Idempotent. Couvre les deux
stockages : les menus en clair *legacy* (``weekly_menus``/``menu_slots``) ET les
blobs de menu **chiffrés** (collection « weekly_menu » du coffre E2E).
"""

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encrypted_blob import EncryptedBlob
from app.models.menu_slot import MenuSlot
from app.models.weekly_menu import WeeklyMenu

logger = logging.getLogger(__name__)


async def erase_by_accounts(session: AsyncSession, account_ids: list[str]) -> int:
    """Supprime les menus (clairs *et* chiffrés) des comptes ciblés.

    Retourne le nombre total d'éléments supprimés (menus en clair + blobs
    chiffrés) — ``0`` si rien ne correspond (idempotent). Aucun court-circuit :
    après la bascule E2E, il n'y a plus de menu en clair mais il faut TOUJOURS
    purger les blobs.
    """
    if not account_ids:
        return 0

    deleted = 0

    # 1) Menus en clair legacy (peut être vide après la bascule E2E).
    result = await session.execute(
        select(WeeklyMenu.id).where(WeeklyMenu.account_id.in_(account_ids))
    )
    menu_ids = list(result.scalars().all())
    if menu_ids:
        await session.execute(delete(MenuSlot).where(MenuSlot.menu_id.in_(menu_ids)))
        await session.execute(delete(WeeklyMenu).where(WeeklyMenu.id.in_(menu_ids)))
        deleted += len(menu_ids)

    # 2) Blobs de menu chiffrés (collection « weekly_menu »), adressés par
    #    account_id (colonne UUID) : on coerce les identifiants en UUID.
    account_uuids: list[uuid.UUID] = []
    for account_id in account_ids:
        try:
            account_uuids.append(uuid.UUID(str(account_id)))
        except (ValueError, TypeError):
            continue
    if account_uuids:
        blob_result = await session.execute(
            delete(EncryptedBlob).where(EncryptedBlob.account_id.in_(account_uuids))
        )
        deleted += blob_result.rowcount or 0

    await session.commit()
    logger.info("Effacement RGPD service-menu : %d élément(s) supprimé(s)", deleted)
    return deleted
