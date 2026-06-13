"""Tâche Celery de purge de rétention (RGPD art. 5.1.e, Phase 4) — service-notification.

Planifiée via le ``beat_schedule`` de ``celery_app`` (worker lancé avec ``-B``).
Ouvre une session dédiée et délègue à ``retention_service``.
"""

import asyncio
import logging

from celery_app import celery_app

from app.core.config import settings
from app.db.session import _session_factory
from app.services import retention_service

logger = logging.getLogger(__name__)


@celery_app.task(name="retention.purge_old_notifications")
def purge_old_notifications() -> int:
    """Purge quotidienne de l'historique des notifications au-delà de la rétention."""

    async def _main() -> int:
        async with _session_factory()() as session:
            return await retention_service.purge_old_notifications(
                session, settings.NOTIFICATION_RETENTION_DAYS
            )

    return asyncio.run(_main())
