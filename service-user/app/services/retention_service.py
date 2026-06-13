"""Purges de rétention (RGPD art. 5.1.e) — service-user.

Fonctions asynchrones testables ; les tâches Celery (``app/tasks/retention.py``)
les invoquent sur une session dédiée selon le planning beat. Toutes idempotentes
(suppriment uniquement ce qui dépasse la rétention/expiration).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AuditLog, Invitation
from app.models.mfa_pending_code import MfaPendingCode
from app.models.password_reset_token import PasswordResetToken

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def purge_expired_auth_tokens(session: AsyncSession) -> int:
    """Supprime les jetons de reset et codes MFA dont l'expiration est dépassée."""
    now = _utcnow()
    total = 0
    for model in (PasswordResetToken, MfaPendingCode):
        result = await session.execute(delete(model).where(model.expires_at < now))
        total += result.rowcount or 0
    await session.commit()
    logger.info("Rétention : %d jeton(s)/code(s) expiré(s) purgé(s)", total)
    return total


async def purge_stale_invitations(session: AsyncSession, retention_days: int) -> int:
    """Supprime les invitations non acceptées au-delà de la rétention."""
    cutoff = _utcnow() - timedelta(days=retention_days)
    result = await session.execute(
        delete(Invitation).where(
            Invitation.created_at < cutoff,
            Invitation.status != "accepted",
        )
    )
    await session.commit()
    deleted = result.rowcount or 0
    logger.info("Rétention : %d invitation(s) obsolète(s) purgée(s)", deleted)
    return deleted


async def purge_old_audit_logs(session: AsyncSession, retention_days: int) -> int:
    """Supprime les entrées d'audit au-delà de la rétention."""
    cutoff = _utcnow() - timedelta(days=retention_days)
    result = await session.execute(
        delete(AuditLog).where(AuditLog.created_at < cutoff)
    )
    await session.commit()
    deleted = result.rowcount or 0
    logger.info("Rétention : %d entrée(s) d'audit ancienne(s) purgée(s)", deleted)
    return deleted
