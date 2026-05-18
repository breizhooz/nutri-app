import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import NotificationStatus, NotificationType
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.dispatch_service import DispatchResult


class TestNotifyRoute:
    @pytest.mark.unit
    async def test_notify_user_not_found_returns_404(
        self, service_client: AsyncClient
    ):
        """POST /api/v1/notify → 404 si aucun device abonné pour ce user."""
        resp = await service_client.post("/api/v1/notify", json={
            "user_slug": str(uuid.UUID("00000000-0000-0000-0000-000000000099")),
            "type": "macro_error",
            "title": "Test",
            "body": "Test body",
        })
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_notify_invalid_user_slug_returns_422(
        self, service_client: AsyncClient
    ):
        """user_slug non parseable en UUID → 422."""
        resp = await service_client.post("/api/v1/notify", json={
            "user_slug": "jean-dupont",
            "type": "macro_error",
            "title": "T", "body": "B",
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_notify_invalid_type_returns_422(
        self, service_client: AsyncClient
    ):
        """Type de notification inexistant → 422 (validation Pydantic)."""
        resp = await service_client.post("/api/v1/notify", json={
            "user_slug": str(uuid.uuid4()),
            "type": "type_inexistant",
            "title": "T", "body": "B",
        })
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_notify_requires_service_token(self, client: AsyncClient):
        """Appel avec JWT utilisateur (pas service token) → 403."""
        resp = await client.post("/api/v1/notify", json={
            "user_slug": str(uuid.uuid4()),
            "type": "macro_error",
            "title": "T", "body": "B",
        })
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_notify_requires_auth_at_all(self):
        """Appel sans Authorization header → 403."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/v1/notify", json={
                "user_slug": str(uuid.uuid4()),
                "type": "macro_error",
                "title": "T", "body": "B",
            })
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_notify_success_returns_200_with_sent_count(
        self, service_client: AsyncClient, db_session
    ):
        """Dispatch réussi → 200, sent=1, status=sent."""
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # Crée une subscription réelle dans la DB de test
        await SubscriptionRepository(db_session).create(
            user_id=user_id,
            endpoint="https://fcm.googleapis.com/fcm/send/notify-test",
            p256dh_key="p256dh",
            auth_key="auth",
            device_label="Test Device",
        )

        mock_result = DispatchResult(
            notification_slug="macro-error-00000000-20260518",
            status=NotificationStatus.SENT,
            sent=1,
            failed=0,
        )
        with patch("app.api.routes.notify.DispatchService") as MockDispatch:
            MockDispatch.return_value.dispatch = AsyncMock(return_value=mock_result)
            resp = await service_client.post("/api/v1/notify", json={
                "user_slug": str(user_id),
                "type": "macro_error",
                "title": "Ingrédient non reconnu",
                "body": "Gochujank introuvable",
                "data": {"macro_error_slug": "gochujank-20260518"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 1
        assert data["failed"] == 0
        assert data["status"] == "sent"
        assert "slug" in data