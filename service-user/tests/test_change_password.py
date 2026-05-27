"""Tests for POST /api/v1/users/me/password — authenticated password change."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


async def _seed_user(session: AsyncSession, password: str = "OldPass1!") -> User:
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="change@test.com",
        hashed_password=hash_password(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.unit
async def test_change_password_success(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    resp = await auth_client.post(
        "/api/v1/users/me/password",
        json={"current_password": "OldPass1!", "new_password": "NewPass99!"},
    )
    assert resp.status_code == 200
    assert "succès" in resp.json()["message"]


@pytest.mark.unit
async def test_change_password_wrong_current(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    resp = await auth_client.post(
        "/api/v1/users/me/password",
        json={"current_password": "WrongPass!", "new_password": "NewPass99!"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["error"]["message"].lower()


@pytest.mark.unit
async def test_change_password_too_short(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    resp = await auth_client.post(
        "/api/v1/users/me/password",
        json={"current_password": "OldPass1!", "new_password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.unit
async def test_change_password_reuse_rejected(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session, password="OldPass1!")
    resp = await auth_client.post(
        "/api/v1/users/me/password",
        json={"current_password": "OldPass1!", "new_password": "OldPass1!"},
    )
    assert resp.status_code == 409
    assert "différent" in resp.json()["error"]["message"]


@pytest.mark.unit
async def test_change_password_unauthenticated() -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/users/me/password",
            json={"current_password": "OldPass1!", "new_password": "NewPass99!"},
        )
    assert resp.status_code == 403
