"""Tests de la purge de rétention (RGPD art. 5.1.e, Phase 4) — service-notification."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import Notification
from app.services import retention_service


def _dt(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _notif(slug: str, created_at: datetime) -> Notification:
    return Notification(
        slug=slug,
        user_id=uuid.uuid4(),
        type=NotificationType.SYSTEM,
        title="t",
        body="b",
        status=NotificationStatus.SENT,
        created_at=created_at,
    )


@pytest.mark.unit
async def test_purge_old_notifications(db_session):
    """Seules les notifications au-delà de la rétention sont supprimées."""
    db_session.add_all(
        [
            _notif("notif-old", _dt(-400)),
            _notif("notif-recent", _dt(-10)),
        ]
    )
    await db_session.commit()

    deleted = await retention_service.purge_old_notifications(
        db_session, retention_days=365
    )
    assert deleted == 1
    remaining = (await db_session.execute(select(Notification.slug))).scalars().all()
    assert remaining == ["notif-recent"]


@pytest.mark.unit
async def test_purge_is_idempotent(db_session):
    """Aucune notification ancienne → rien à supprimer (idempotent)."""
    db_session.add(_notif("notif-recent", _dt(-1)))
    await db_session.commit()

    deleted = await retention_service.purge_old_notifications(
        db_session, retention_days=365
    )
    assert deleted == 0
