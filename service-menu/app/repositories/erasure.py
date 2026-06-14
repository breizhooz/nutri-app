"""Effacement RGPD (art. 17) — purge des menus d'un compte.

Sert l'endpoint interne appelé par service-user. Idempotent.
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu_slot import MenuSlot
from app.models.weekly_menu import WeeklyMenu

logger = logging.getLogger(__name__)


async def erase_by_accounts(session: AsyncSession, account_ids: list[str]) -> int:
    """Supprime les menus (et leurs créneaux) des comptes ciblés.

    Retourne le nombre de menus supprimés — ``0`` si rien ne correspond
    (idempotent). Les créneaux sont supprimés explicitement (la cascade ORM ne
    s'applique pas aux DELETE en masse).
    """
    if not account_ids:
        return 0
    result = await session.execute(
        select(WeeklyMenu.id).where(WeeklyMenu.account_id.in_(account_ids))
    )
    menu_ids = list(result.scalars().all())
    if not menu_ids:
        return 0

    await session.execute(delete(MenuSlot).where(MenuSlot.menu_id.in_(menu_ids)))
    await session.execute(delete(WeeklyMenu).where(WeeklyMenu.id.in_(menu_ids)))
    await session.commit()
    logger.info("Effacement RGPD service-menu : %d menu(s) supprimé(s)", len(menu_ids))
    return len(menu_ids)
