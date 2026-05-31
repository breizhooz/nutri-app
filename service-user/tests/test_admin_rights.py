"""Tests for the admin RBAC endpoints and rights logic."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user_service import UserService

# Matches conftest.TEST_USER_ID embedded in make_test_token() used by auth_client.
ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _add_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    email: str,
    admin: bool = False,
) -> User:
    user = User(id=user_id, email=email, hashed_password="x", user_admin=admin)
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_list_users_forbidden_for_non_admin(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="me@test.io", admin=False)
    resp = await auth_client.get("/api/v1/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_as_admin_returns_rights(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    await _add_user(db_session, user_id=uuid.uuid4(), email="bob@test.io")

    resp = await auth_client.get("/api/v1/users")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    bob = next(u for u in data if u["email"] == "bob@test.io")
    assert bob["user_admin"] is False
    assert bob["user_right"]["crawl"] == {"instagram": False, "web": False}


@pytest.mark.asyncio
async def test_update_user_rights_grants_crawl(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    target_id = uuid.uuid4()
    await _add_user(db_session, user_id=target_id, email="bob@test.io")

    resp = await auth_client.patch(
        f"/api/v1/users/{target_id}/rights",
        json={"user_right": {"crawl": {"instagram": True, "web": False}}},
    )
    assert resp.status_code == 200
    assert resp.json()["user_right"]["crawl"] == {"instagram": True, "web": False}


@pytest.mark.asyncio
async def test_update_user_admin_flag(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    target_id = uuid.uuid4()
    await _add_user(db_session, user_id=target_id, email="bob@test.io")

    resp = await auth_client.patch(
        f"/api/v1/users/{target_id}/rights", json={"user_admin": True}
    )
    assert resp.status_code == 200
    assert resp.json()["user_admin"] is True


@pytest.mark.asyncio
async def test_update_rights_forbidden_for_non_admin(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="me@test.io", admin=False)
    resp = await auth_client.patch(
        f"/api/v1/users/{uuid.uuid4()}/rights", json={"user_admin": True}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_rights_user_not_found(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    resp = await auth_client.patch(
        f"/api/v1/users/{uuid.uuid4()}/rights", json={"user_admin": True}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_me_exposes_rights(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="me@test.io", admin=False)
    resp = await auth_client.get("/api/v1/users/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_admin"] is False
    assert body["user_right"]["crawl"] == {"instagram": False, "web": False}


@pytest.mark.asyncio
async def test_delete_own_account(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="me@test.io", admin=False)
    resp = await auth_client.delete(f"/api/v1/users/{ADMIN_ID}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_deletes_other_account(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    target_id = uuid.uuid4()
    await _add_user(db_session, user_id=target_id, email="bob@test.io")

    resp = await auth_client.delete(f"/api/v1/users/{target_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_other_account_forbidden_for_non_admin(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="me@test.io", admin=False)
    resp = await auth_client.delete(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_delete_user_not_found(db_session, auth_client):
    await _add_user(db_session, user_id=ADMIN_ID, email="admin@test.io", admin=True)
    resp = await auth_client.delete(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_service_delete_user_returns_false_when_missing():
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    service = UserService(repo)

    assert await service.delete_user(uuid.uuid4()) is False
    repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_service_delete_user_deletes_when_found():
    repo = AsyncMock()
    repo.get_by_id.return_value = User(id=uuid.uuid4(), email="x@y.io")
    service = UserService(repo)

    assert await service.delete_user(uuid.uuid4()) is True
    repo.delete.assert_awaited_once()


def test_build_token_claims_reads_user_fields():
    class _U:
        user_admin = True
        user_right = {"crawl": {"instagram": True, "web": False}}

    claims = UserService.build_token_claims(_U())
    assert claims == {
        "user_admin": True,
        "user_right": {"crawl": {"instagram": True, "web": False}},
    }
