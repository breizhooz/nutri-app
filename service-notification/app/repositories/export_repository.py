"""Export RGPD (art. 20, portabilité) — données notification d'un utilisateur.

Sert l'endpoint interne appelé par service-user. Lecture seule, miroir de
``ErasureRepository``. Les clés cryptographiques des abonnements push
(``p256dh_key``, ``auth_key``) sont des secrets techniques et sont exclues.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)

# Colonnes secrètes des abonnements push, jamais exportées.
_SUBSCRIPTION_SECRET_COLS = {"p256dh_key", "auth_key"}


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


def _row_to_dict(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """Sérialise une ligne ORM en dict JSON-able (colonnes uniquement)."""
    exclude = exclude or set()
    return {
        col.name: _json_value(getattr(obj, col.name))
        for col in obj.__table__.columns
        if col.name not in exclude
    }


class ExportRepository:
    """Assemble l'export des données notification d'un utilisateur (art. 20)."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def export_by_user(self, user_id: uuid.UUID | None) -> dict[str, Any]:
        """Retourne notifications + abonnements de l'utilisateur.

        ``{"notifications": [...], "subscriptions": [...]}`` (listes vides si
        ``user_id`` absent ou rien ne correspond).
        """
        if user_id is None:
            return {"notifications": [], "subscriptions": []}

        notif_rows = await self._session.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        sub_rows = await self._session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        notifications = [_row_to_dict(n) for n in notif_rows.scalars()]
        subscriptions = [
            _row_to_dict(s, exclude=_SUBSCRIPTION_SECRET_COLS)
            for s in sub_rows.scalars()
        ]
        logger.info(
            "Export RGPD service-notification : %d notif(s), %d abonnement(s)",
            len(notifications),
            len(subscriptions),
        )
        return {"notifications": notifications, "subscriptions": subscriptions}
