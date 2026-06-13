"""Tests de l'endpoint interne d'effacement RGPD (art. 17) — service-notification."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.repositories.notification_repository import NotificationRepository

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000011")


async def _seed(db_session, user_id: uuid.UUID) -> None:
    """Crée une notification + un abonnement pour l'utilisateur."""
    await NotificationRepository(db_session).create(
        user_id=user_id,
        type=NotificationType.SYSTEM,
        title="Titre",
        body="Corps",
    )
    db_session.add(
        Subscription(
            slug=f"sub-{user_id}",
            user_id=user_id,
            endpoint=f"https://push.example/{user_id}",
            p256dh_key="p256dh",
            auth_key="auth",
        )
    )
    await db_session.commit()


@pytest.mark.unit
async def test_erasure_removes_user_data(service_client, db_session):
    """L'effacement supprime notifications + abonnements de l'utilisateur ciblé."""
    await _seed(db_session, TEST_USER_ID)
    await _seed(db_session, OTHER_USER_ID)

    resp = await service_client.post(
        "/api/v1/internal/erasure", json={"user_id": str(TEST_USER_ID)}
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2  # 1 notification + 1 abonnement

    # Les données de l'autre utilisateur subsistent.
    remaining = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == OTHER_USER_ID)
        )
    ).scalar()
    assert remaining == 1


@pytest.mark.unit
async def test_erasure_is_idempotent(service_client, db_session):
    """Un second appel ne supprime rien (deleted=0)."""
    await _seed(db_session, TEST_USER_ID)
    body = {"user_id": str(TEST_USER_ID)}

    first = await service_client.post("/api/v1/internal/erasure", json=body)
    assert first.json()["deleted"] == 2
    second = await service_client.post("/api/v1/internal/erasure", json=body)
    assert second.status_code == 200
    assert second.json()["deleted"] == 0


@pytest.mark.unit
async def test_erasure_rejects_user_token(client):
    """Un JWT utilisateur (et non un token de service) est refusé (403)."""
    resp = await client.post(
        "/api/v1/internal/erasure", json={"user_id": str(TEST_USER_ID)}
    )
    assert resp.status_code == 403
