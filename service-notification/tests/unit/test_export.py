"""Tests de l'export RGPD (art. 20) — service-notification."""

import uuid

import pytest

from app.models.enums import NotificationStatus, NotificationType
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.repositories.export_repository import ExportRepository


def _notif(user_id, slug):
    return Notification(
        slug=slug,
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title="t",
        body="b",
        status=NotificationStatus.SENT,
    )


def _sub(user_id, slug):
    return Subscription(
        slug=slug,
        user_id=user_id,
        endpoint=f"https://push/{slug}",
        p256dh_key="SECRET-P256",
        auth_key="SECRET-AUTH",
    )


@pytest.mark.unit
async def test_export_returns_user_data_without_secrets(db_session):
    """L'export renvoie notifs + abonnements, sans les clés cryptographiques."""
    uid = uuid.uuid4()
    other = uuid.uuid4()
    db_session.add_all([_notif(uid, "n-1"), _notif(other, "n-2"), _sub(uid, "s-1")])
    await db_session.commit()

    data = await ExportRepository(db_session).export_by_user(uid)
    assert {n["slug"] for n in data["notifications"]} == {"n-1"}
    assert len(data["subscriptions"]) == 1
    sub = data["subscriptions"][0]
    assert sub["endpoint"] == "https://push/s-1"
    assert "p256dh_key" not in sub
    assert "auth_key" not in sub


@pytest.mark.unit
async def test_export_empty_for_unknown_user(db_session):
    """Utilisateur inconnu / absent → listes vides."""
    assert await ExportRepository(db_session).export_by_user(None) == {
        "notifications": [],
        "subscriptions": [],
    }
    data = await ExportRepository(db_session).export_by_user(uuid.uuid4())
    assert data == {"notifications": [], "subscriptions": []}
