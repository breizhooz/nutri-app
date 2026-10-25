"""Effacement RGPD (art. 17) — purge des menus d'un compte.

Sert l'endpoint interne appelé par service-user. Idempotent : supprime les
menus (``weekly_menus``/``menu_slots``) des comptes ciblés.
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu_slot import MenuSlot
from app.models.weekly_menu import WeeklyMenu

logger = logging.getLogger(__name__)


async def erase_by_accounts(session: AsyncSession, account_ids: list[str]) -> int:
    """Supprime les menus des comptes ciblés ; ``0`` si rien (idempotent)."""
    if not account_ids:
        return 0

    deleted = 0

    result = await session.execute(
        select(WeeklyMenu.id).where(WeeklyMenu.account_id.in_(account_ids))
    )
    menu_ids = list(result.scalars().all())
    if menu_ids:
        await session.execute(delete(MenuSlot).where(MenuSlot.menu_id.in_(menu_ids)))
        await session.execute(delete(WeeklyMenu).where(WeeklyMenu.id.in_(menu_ids)))
        deleted += len(menu_ids)

    await session.commit()
    logger.info("Effacement RGPD service-menu : %d élément(s) supprimé(s)", deleted)
    return deleted
