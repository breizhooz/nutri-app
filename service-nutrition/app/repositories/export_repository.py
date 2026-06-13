"""Export RGPD (art. 20, portabilité) — données nutrition d'un compte.

Sert l'endpoint interne appelé par service-user. Lecture seule, miroir de
``ErasureRepository``. ``nutrition_items`` (source utilisateur) sont des données
de référence non personnelles → hors périmètre, comme pour l'effacement.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro_error import MacroError

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


class ExportRepository:
    """Assemble l'export des données nutrition d'un compte (art. 20)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def export_by_accounts(
        self, account_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Retourne les macro_errors ciblés par ``account_id`` ou ``user_id``.

        ``{"macro_errors": [...]}`` (liste vide si rien ne correspond).
        """
        filters = []
        if account_ids:
            filters.append(MacroError.account_id.in_(account_ids))
        if user_id is not None:
            filters.append(MacroError.user_id == user_id)
        if not filters:
            return {"macro_errors": []}

        rows = await self._session.execute(select(MacroError).where(or_(*filters)))
        macro_errors = [_row_to_dict(m) for m in rows.scalars()]
        logger.info(
            "Export RGPD service-nutrition : %d macro_error(s)", len(macro_errors)
        )
        return {"macro_errors": macro_errors}
