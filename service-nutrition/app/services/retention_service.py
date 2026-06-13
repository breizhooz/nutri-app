"""Purge de rétention (RGPD art. 5.1.e, Phase 4) — service-nutrition.

Fonction async testable ; la tâche Celery (``app/tasks/retention.py``) l'invoque
sur une session dédiée selon le planning beat.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro_error import MacroError

logger = logging.getLogger(__name__)


async def purge_old_macro_errors(session: AsyncSession, retention_days: int) -> int:
    """Supprime les diagnostics macro_errors au-delà de la rétention. Idempotent."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await session.execute(
        delete(MacroError).where(MacroError.created_at < cutoff)
    )
    await session.commit()
    deleted = result.rowcount or 0
    logger.info("Rétention : %d macro_error(s) ancienne(s) purgée(s)", deleted)
    return deleted
