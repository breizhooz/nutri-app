"""Purge de rétention (RGPD art. 5.1.e, Phase 4) — service-notification.

Fonction async testable ; la tâche Celery (``app/tasks/retention.py``) l'invoque
sur une session dédiée selon le planning beat. Idempotente.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def purge_old_notifications(session: AsyncSession, retention_days: int) -> int:
    """Supprime l'historique des notifications au-delà de la rétention. Idempotent."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        delete(Notification).where(Notification.created_at < cutoff)
    )
    await session.commit()
    deleted = result.rowcount or 0
    logger.info("Rétention : %d notification(s) ancienne(s) purgée(s)", deleted)
    return deleted
