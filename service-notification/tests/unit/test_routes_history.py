import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import NotificationType
from app.repositories.notification_repository import NotificationRepository

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class TestHistoryRoute:
    @pytest.mark.unit
    async def test_get_history_empty_returns_200(self, client):
        """Aucune notification → 200 avec liste vide."""
        resp = await client.get(f"/api/v1/users/{TEST_USER_ID}/history")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.unit
    async def test_get_history_returns_created_notifications(
        self, client, db_session
    ):
        """Notifications en base → retournées dans la réponse."""
        repo = NotificationRepository(db_session)
        await repo.create(
            user_id=TEST_USER_ID,
            type=NotificationType.MACRO_ERROR,
            title="Ingrédient non reconnu",
            body="Gochujank introuvable",
            data={"macro_error_slug": "gochujank-20260518"},
        )
        await repo.create(
            user_id=TEST_USER_ID,
            type=NotificationType.CRAWL_DONE,
            title="Crawl terminé",
            body="3 recettes disponibles",
        )
        resp = await client.get(f"/api/v1/users/{TEST_USER_ID}/history")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        assert {i["type"] for i in items} == {"macro_error", "crawl_done"}

    @pytest.mark.unit
    async def test_get_history_invalid_user_slug_returns_422(self, client):
        """user_slug non parseable en UUID → 422."""
        resp = await client.get("/api/v1/users/jean-dupont/history")
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_get_history_other_user_returns_403(self, client):
        """Accès à l'historique d'un autre user → 403."""
        resp = await client.get(f"/api/v1/users/{OTHER_USER_ID}/history")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_get_history_requires_auth(self):
        """Sans Authorization header → 403."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(f"/api/v1/users/{TEST_USER_ID}/history")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_get_history_limit_pagination(self, client, db_session):
        """limit=1 → 1 seule notification retournée."""
        repo = NotificationRepository(db_session)
        for i in range(3):
            await repo.create(
                user_id=TEST_USER_ID,
                type=NotificationType.SYSTEM,
                title=f"Notif {i}",
                body="B",
            )
        resp = await client.get(
            f"/api/v1/users/{TEST_USER_ID}/history", params={"limit": 1}
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.unit
    async def test_get_history_offset_pagination(self, client, db_session):
        """offset=2 sur 3 notifications → 1 retournée."""
        repo = NotificationRepository(db_session)
        for i in range(3):
            await repo.create(
                user_id=TEST_USER_ID,
                type=NotificationType.SYSTEM,
                title=f"Notif {i}",
                body="B",
            )
        resp = await client.get(
            f"/api/v1/users/{TEST_USER_ID}/history", params={"offset": 2}
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.unit
    async def test_get_history_ordered_desc(self, client, db_session):
        """Les notifications sont retournées du plus récent au plus ancien."""
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import update as sa_update
        from app.models.notification import Notification

        repo = NotificationRepository(db_session)
        n1 = await repo.create(
            user_id=TEST_USER_ID,
            type=NotificationType.SYSTEM,
            title="Premier",
            body="B",
        )
        await repo.create(
            user_id=TEST_USER_ID,
            type=NotificationType.SYSTEM,
            title="Deuxième",
            body="B",
        )

        # Même raison : func.now() identique sur SQLite in-memory.
        await db_session.execute(
            sa_update(Notification)
            .where(Notification.id == n1.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        )
        await db_session.commit()

        resp = await client.get(f"/api/v1/users/{TEST_USER_ID}/history")
        items = resp.json()
        assert items[0]["title"] == "Deuxième"
        assert items[1]["title"] == "Premier"