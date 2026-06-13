"""Agrégation de l'export RGPD (art. 20, portabilité) — service-user.

Rassemble dans un seul document JSON les données personnelles de l'utilisateur :
son identité (service-user) + ses données détenues par les autres microservices
(profil/santé, menus, notifications, nutrition), récupérées via ``ExportClient``.

Best-effort cross-service : si un service est indisponible, son entrée porte une
clé ``error`` au lieu des données, sans faire échouer l'export global.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Account, Membership
from app.models.consent import Consent
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.export_client import EXPORT_SERVICES, ExportClient

logger = logging.getLogger(__name__)

# Colonnes secrètes de l'identité, jamais exportées.
_USER_SECRET_COLS = {"hashed_password", "totp_secret"}


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


class ExportService:
    """Construit l'export agrégé des données personnelles d'un utilisateur."""

    def __init__(
        self, session: AsyncSession, client: ExportClient | None = None
    ) -> None:
        self.session = session
        self._client = client or ExportClient()

    async def build_export(self, user: User) -> dict[str, Any]:
        """Assemble l'identité + les données cross-service de ``user``."""
        account_ids = await UserRepository(self.session).list_personal_account_ids(user)
        account_ids_str = [str(a) for a in account_ids]
        user_id_str = str(user.id)

        export: dict[str, Any] = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "user": await self._identity(user, account_ids),
        }
        export["services"] = await self._cross_service(account_ids_str, user_id_str)
        return export

    async def _identity(
        self, user: User, account_ids: list[uuid.UUID]
    ) -> dict[str, Any]:
        """Données détenues par service-user (sans secrets)."""
        accounts = (
            await self.session.execute(
                select(Account).where(Account.id.in_(account_ids))
            )
        ).scalars()
        memberships = (
            await self.session.execute(
                select(Membership).where(Membership.identity_id == user.id)
            )
        ).scalars()
        consents = (
            await self.session.execute(
                select(Consent).where(Consent.user_id == user.id)
            )
        ).scalars()
        return {
            "identity": _row_to_dict(user, exclude=_USER_SECRET_COLS),
            "accounts": [_row_to_dict(a) for a in accounts],
            "memberships": [_row_to_dict(m) for m in memberships],
            "consents": [_row_to_dict(c) for c in consents],
        }

    async def _cross_service(
        self, account_ids: list[str], user_id: str
    ) -> dict[str, Any]:
        """Récupère les données de chaque service détenteur (best-effort)."""
        services: dict[str, Any] = {}
        for service in EXPORT_SERVICES:
            try:
                services[service] = await self._client.export(
                    service, account_ids, user_id
                )
            except Exception as exc:  # noqa: BLE001 — best-effort, on note l'échec
                logger.warning("Export %s échoué : %s", service, exc)
                services[service] = {"error": str(exc)}
        return services
