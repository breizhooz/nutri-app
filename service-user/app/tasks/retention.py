"""Tâches Celery de purge de rétention (RGPD art. 5.1.e, Phase 4) — service-user.

Planifiées via ``celery_app.conf.beat_schedule`` (worker lancé avec ``-B``).
Chaque tâche ouvre une session dédiée et délègue à ``retention_service``.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app

from app.core.config import settings
from app.db.session import _session_factory
from app.services import retention_service

logger = logging.getLogger(__name__)


def _run(job: Callable[[AsyncSession], Awaitable[int]]) -> int:
    """Exécute une purge async sur une session dédiée et retourne le compte."""

    async def _main() -> int:
        async with _session_factory()() as session:
            return await job(session)

    return asyncio.run(_main())


@celery_app.task(name="retention.purge_expired_auth_tokens")
def purge_expired_auth_tokens() -> int:
    """Purge horaire des jetons de reset et codes MFA expirés."""
    return _run(retention_service.purge_expired_auth_tokens)


@celery_app.task(name="retention.purge_stale_invitations")
def purge_stale_invitations() -> int:
    """Purge quotidienne des invitations non acceptées obsolètes."""
    return _run(
        lambda s: retention_service.purge_stale_invitations(
            s, settings.INVITATION_RETENTION_DAYS
        )
    )


@celery_app.task(name="retention.purge_old_audit_logs")
def purge_old_audit_logs() -> int:
    """Purge quotidienne des entrées d'audit au-delà de la rétention."""
    return _run(
        lambda s: retention_service.purge_old_audit_logs(
            s, settings.AUDIT_LOG_RETENTION_DAYS
        )
    )
