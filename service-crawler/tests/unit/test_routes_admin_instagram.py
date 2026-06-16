import pytest
from httpx import AsyncClient

from app.api.routes.admin import InstagramSessionServiceFactory
from app.core.deps import get_token_payload
from app.main import app
from app.services.instagram_session_service import InstagramSessionError


async def _admin_payload() -> dict:
    return {
        "sub": "00000000-0000-0000-0000-000000000001",
        "type": "access",
        "user_admin": True,
    }


class _OkService:
    def update_session(self, session_id: str, username=None) -> str:
        return "bob"

    def session_info(self):
        from app.schemas.instagram import InstagramSessionInfo

        return InstagramSessionInfo(
            configured=True, username="bob", updated_at="2026-05-30T10:00:00+00:00"
        )


class _FailService:
    def update_session(self, session_id: str, username=None) -> str:
        raise InstagramSessionError("Session invalide ou expirée.")


@pytest.mark.asyncio
async def test_update_session_forbidden_for_non_admin(client: AsyncClient):
    resp = await client.post(
        "/api/v1/crawler/admin/instagram/session", json={"session_id": "SID"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_session_ok_for_admin(client: AsyncClient):
    app.dependency_overrides[get_token_payload] = _admin_payload
    app.dependency_overrides[InstagramSessionServiceFactory.inject] = lambda: (
        _OkService()
    )

    resp = await client.post(
        "/api/v1/crawler/admin/instagram/session", json={"session_id": "SID"}
    )

    assert resp.status_code == 200
    assert resp.json() == {"username": "bob"}


@pytest.mark.asyncio
async def test_update_session_invalid_returns_400(client: AsyncClient):
    app.dependency_overrides[get_token_payload] = _admin_payload
    app.dependency_overrides[InstagramSessionServiceFactory.inject] = lambda: (
        _FailService()
    )

    resp = await client.post(
        "/api/v1/crawler/admin/instagram/session", json={"session_id": "SID"}
    )

    assert resp.status_code == 400
    assert "invalide" in resp.text.lower()


@pytest.mark.asyncio
async def test_get_session_info_forbidden_for_non_admin(client: AsyncClient):
    resp = await client.get("/api/v1/crawler/admin/instagram/session")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_session_info_ok_for_admin(client: AsyncClient):
    app.dependency_overrides[get_token_payload] = _admin_payload
    app.dependency_overrides[InstagramSessionServiceFactory.inject] = lambda: (
        _OkService()
    )

    resp = await client.get("/api/v1/crawler/admin/instagram/session")

    assert resp.status_code == 200
    assert resp.json() == {
        "configured": True,
        "username": "bob",
        "updated_at": "2026-05-30T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_update_session_requires_session_id(client: AsyncClient):
    app.dependency_overrides[get_token_payload] = _admin_payload

    resp = await client.post("/api/v1/crawler/admin/instagram/session", json={})

    assert resp.status_code == 422
