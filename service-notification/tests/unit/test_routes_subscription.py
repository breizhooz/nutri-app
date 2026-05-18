import uuid 

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

class TestSubscriptionsRoutes:
    @pytest.mark.unit
    async def test_create_subscription_returns_201(self, client: AsyncClient):
        """POST /api/v1/subscriptions → 201 avec slug généré."""
        resp = await client.post("/api/v1/subscriptions", json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
            "p256dh_key": "BNcTestKey",
            "auth_key": "TestAuth",
            "device_label": "Chrome Desktop",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "slug" in data
        assert data["endpoint"] == "https://fcm.googleapis.com/fcm/send/abc"
        assert data["device_label"] == "Chrome Desktop"

    @pytest.mark.unit
    async def test_create_subscription_idempotent_on_same_endpoint(
        self, client: AsyncClient
    ):
        """Deux inscriptions sur le même endpoint → même slug retourné (pas de doublon)."""
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/idempotent",
            "p256dh_key": "key",
            "auth_key": "auth",
        }
        r1 = await client.post("/api/v1/subscriptions", json=payload)
        r2 = await client.post("/api/v1/subscriptions", json=payload)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["slug"] == r2.json()["slug"]

    @pytest.mark.unit
    async def test_get_subscription_not_found_returns_404(self, client: AsyncClient):
        """GET /api/v1/subscriptions/inexistant → 404."""
        resp = await client.get("/api/v1/subscriptions/slug-inexistant")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_subscription_returns_200(self, client: AsyncClient):
        """GET /api/v1/subscriptions/{slug} → 200 avec les bonnes données."""
        create = await client.post("/api/v1/subscriptions", json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/get-test",
            "p256dh_key": "p256dh",
            "auth_key": "auth",
            "device_label": "Safari iPhone",
        })
        slug = create.json()["slug"]
        get = await client.get(f"/api/v1/subscriptions/{slug}")
        assert get.status_code == 200
        assert get.json()["slug"] == slug
        assert get.json()["device_label"] == "Safari iPhone"

    @pytest.mark.unit
    async def test_delete_subscription_returns_204(self, client: AsyncClient):
        """DELETE /api/v1/subscriptions/{slug} → 204, puis 404 au GET."""
        slug = (await client.post("/api/v1/subscriptions", json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/delete-test",
            "p256dh_key": "k", "auth_key": "a",
        })).json()["slug"]

        assert (await client.delete(f"/api/v1/subscriptions/{slug}")).status_code == 204
        assert (await client.get(f"/api/v1/subscriptions/{slug}")).status_code == 404

    @pytest.mark.unit
    async def test_delete_subscription_not_found_returns_404(self, client: AsyncClient):
        """DELETE sur un slug inexistant → 404."""
        resp = await client.delete("/api/v1/subscriptions/ghost-slug")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_create_subscription_requires_auth(self):
        """POST sans Authorization header → 403 (HTTPBearer auto_error)."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/v1/subscriptions", json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/noauth",
                "p256dh_key": "k", "auth_key": "a",
            })
        assert resp.status_code == 403
    
    @pytest.mark.unit
    async def test_get_subscription_other_user_returns_403(
        self, client: AsyncClient, db_session
    ):
        """GET d'une subscription appartenant à un autre user → 403."""
        from app.repositories.subscription_repository import SubscriptionRepository
        other_user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        repo = SubscriptionRepository(db_session)
        sub = await repo.create(
            user_id=other_user_id,
            endpoint="https://push.example.com/other-user",
            p256dh_key="k", auth_key="a",
        )
        resp = await client.get(f"/api/v1/subscriptions/{sub.slug}")
        assert resp.status_code == 403

    @pytest.mark.unit
    async def test_delete_subscription_other_user_returns_403(
        self, client: AsyncClient, db_session
    ):
        """DELETE d'une subscription appartenant à un autre user → 403."""
        from app.repositories.subscription_repository import SubscriptionRepository
        other_user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        repo = SubscriptionRepository(db_session)
        sub = await repo.create(
            user_id=other_user_id,
            endpoint="https://push.example.com/other-user-del",
            p256dh_key="k", auth_key="a",
        )
        resp = await client.delete(f"/api/v1/subscriptions/{sub.slug}")
        assert resp.status_code == 403