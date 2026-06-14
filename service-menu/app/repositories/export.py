"""Export RGPD (art. 20, portabilité) — menus d'un compte.

Sert l'endpoint interne appelé par service-user. Lecture seule, miroir de
``erasure.py``.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu_slot import MenuSlot
from app.models.weekly_menu import WeeklyMenu

logger = logging.getLogger(__name__)


def _json_value(value: Any) -> Any:
    """Normalise une valeur de colonne pour la sérialisation JSON."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _row_to_dict(obj: Any) -> dict[str, Any]:
    """Sérialise une ligne ORM en dict JSON-able (colonnes uniquement)."""
    return {
        col.name: _json_value(getattr(obj, col.name)) for col in obj.__table__.columns
    }


async def export_by_accounts(
    session: AsyncSession, account_ids: list[str]
) -> dict[str, Any]:
    """Retourne les menus des comptes ciblés, créneaux imbriqués.

    ``{"weekly_menus": [ {..., "slots": [...]} ]}`` (liste vide si rien).
    """
    if not account_ids:
        return {"weekly_menus": []}

    rows = await session.execute(
        select(WeeklyMenu).where(WeeklyMenu.account_id.in_(account_ids))
    )
    menus = list(rows.scalars())

    export: list[dict[str, Any]] = []
    for menu in menus:
        entry = _row_to_dict(menu)
        slot_rows = await session.execute(
            select(MenuSlot).where(MenuSlot.menu_id == menu.id)
        )
        entry["slots"] = [_row_to_dict(s) for s in slot_rows.scalars()]
        export.append(entry)

    logger.info("Export RGPD service-menu : %d menu(s)", len(export))
    return {"weekly_menus": export}
