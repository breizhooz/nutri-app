"""Purges de rétention (RGPD art. 5.1.e) — service-user.

Fonctions asynchrones testables ; les tâches Celery (``app/tasks/retention.py``)
les invoquent sur une session dédiée selon le planning beat. Toutes idempotentes
(suppriment uniquement ce qui dépasse la rétention/expiration).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AuditLog, Invitation
from app.models.mfa_pending_code import MfaPendingCode
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

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


async def purge_inactive_accounts(session: AsyncSession, retention_days: int) -> int:
    """Efface les comptes inactifs au-delà de la rétention (RGPD art. 5.1.e).

    Un compte est « inactif » si sa dernière activité authentifiée
    (``last_login_at``, à défaut ``created_at``) précède le seuil. Pour chaque
    identité concernée on déclenche l'effacement cross-service complet (réutilise
    la Phase 1 via ``UserService.delete_user`` : journal + audit + purge des
    autres services + suppression locale). Les administrateurs sont exclus
    (garde-fou : pas de suppression automatique d'un compte admin). Idempotent.

    Retourne le nombre de comptes effacés.
    """
    # Import différé : user_service importe ce module indirectement via erasure ;
    # on évite tout cycle au chargement.
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    cutoff = _utcnow() - timedelta(days=retention_days)
    last_activity = func.coalesce(User.last_login_at, User.created_at)
    rows = await session.execute(
        select(User.id).where(last_activity < cutoff, User.user_admin.is_(False))
    )
    user_ids = [r[0] for r in rows.all()]
    if not user_ids:
        return 0

    service = UserService(UserRepository(session))
    purged = 0
    for user_id in user_ids:
        if await service.delete_user(user_id):
            purged += 1
    logger.info("Rétention : %d compte(s) inactif(s) effacé(s)", purged)
    return purged
