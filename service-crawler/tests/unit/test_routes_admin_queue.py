import pytest
from httpx import AsyncClient

from app.api.routes.admin import QueueServiceFactory
from app.core.deps import get_token_payload
from app.main import app
from app.schemas.queue import QueueSnapshot


class _StubQueue:
    def snapshot(self) -> QueueSnapshot:
        return QueueSnapshot(
            workers=["w1"],
            counts={"workers": 1, "active": 0, "scheduled": 1, "reserved": 0},
            active=[],
            scheduled=[],
            reserved=[],
        )


@pytest.mark.asyncio
async def test_queue_forbidden_for_non_admin(client: AsyncClient):
    """Le client par défaut a user_admin=False → 403."""
    resp = await client.get("/api/v1/crawler/admin/queue")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_queue_ok_for_admin(client: AsyncClient):
    async def _admin_payload() -> dict:
        return {"sub": "00000000-0000-0000-0000-000000000001", "type": "access", "user_admin": True}

    app.dependency_overrides[get_token_payload] = _admin_payload
    app.dependency_overrides[QueueServiceFactory.inject] = lambda: _StubQueue()

    resp = await client.get("/api/v1/crawler/admin/queue")

    assert resp.status_code == 200
    body = resp.json()
    assert body["workers"] == ["w1"]
    assert body["counts"]["scheduled"] == 1
