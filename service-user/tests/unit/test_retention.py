"""Tests des purges de rétention (RGPD art. 5.1.e, Phase 4) — service-user."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.access import AuditLog, Invitation
from app.models.mfa_pending_code import MfaPendingCode
from app.models.password_reset_token import PasswordResetToken
from app.services import retention_service


def _dt(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


@pytest.mark.unit
async def test_purge_expired_auth_tokens(db_session):
    """Seuls les jetons/codes dont expires_at est passé sont supprimés."""
    uid = uuid.uuid4()
    db_session.add_all(
        [
            PasswordResetToken(user_id=uid, token_hash="reset-exp", expires_at=_dt(-1)),
            PasswordResetToken(user_id=uid, token_hash="reset-ok", expires_at=_dt(1)),
            MfaPendingCode(user_id=uid, code_hash="mfa-exp", expires_at=_dt(-1)),
            MfaPendingCode(user_id=uid, code_hash="mfa-ok", expires_at=_dt(1)),
        ]
    )
    await db_session.commit()

    deleted = await retention_service.purge_expired_auth_tokens(db_session)
    assert deleted == 2
    assert (
        await db_session.execute(select(func.count()).select_from(PasswordResetToken))
    ).scalar() == 1
    assert (
        await db_session.execute(select(func.count()).select_from(MfaPendingCode))
    ).scalar() == 1


@pytest.mark.unit
async def test_purge_stale_invitations(db_session):
    """Les invitations non acceptées au-delà de la rétention sont supprimées."""
    acc = uuid.uuid4()
    db_session.add_all(
        [
            Invitation(
                account_id=acc, email="old@x.io", role_code="OWNER", token="t-old",
                status="expired", expires_at=_dt(-100), created_at=_dt(-100),
            ),
            Invitation(
                account_id=acc, email="recent@x.io", role_code="OWNER", token="t-recent",
                status="pending", expires_at=_dt(5), created_at=_dt(-1),
            ),
            Invitation(
                account_id=acc, email="acc@x.io", role_code="OWNER", token="t-acc",
                status="accepted", expires_at=_dt(-100), created_at=_dt(-100),
            ),
        ]
    )
    await db_session.commit()

    deleted = await retention_service.purge_stale_invitations(db_session, retention_days=90)
    assert deleted == 1
    remaining = (await db_session.execute(select(Invitation.token))).scalars().all()
    assert set(remaining) == {"t-recent", "t-acc"}


@pytest.mark.unit
async def test_purge_old_audit_logs(db_session):
    """Les entrées d'audit au-delà de la rétention sont supprimées."""
    db_session.add_all(
        [
            AuditLog(action="old", created_at=_dt(-2000)),
            AuditLog(action="recent", created_at=_dt(-1)),
        ]
    )
    await db_session.commit()

    deleted = await retention_service.purge_old_audit_logs(db_session, retention_days=1095)
    assert deleted == 1
    remaining = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert remaining == ["recent"]
