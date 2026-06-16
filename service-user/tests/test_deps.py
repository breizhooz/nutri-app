"""Tests for app/core/deps.py — get_current_user, get_mfa_pending_user, get_mfa_user_id_from_token."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_mfa_pending_user,
    get_mfa_user_id_from_token,
)
from app.core.security import create_mfa_token, hash_password
from app.models.user import User

# Minimal stand-in for a Request when deps are called directly (locale only).
_FAKE_REQUEST = SimpleNamespace(state=SimpleNamespace(locale="fr"))


# ── get_current_user (via /api/v1/users/me) ────────────────────────────────────


@pytest.mark.unit
async def test_get_current_user_valid_token_returns_user(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="deps@test.com",
        hashed_password=hash_password("pw"),
    )
    db_session.add(user)
    await db_session.commit()

    resp = await auth_client.get("/api/v1/users/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "deps@test.com"


@pytest.mark.unit
async def test_get_current_user_invalid_token_returns_401(
    anon_client: AsyncClient,
) -> None:
    resp = await anon_client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer bad.token.here"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_get_current_user_mfa_token_type_returns_401(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    from conftest import TEST_USER_ID

    user = User(
        id=TEST_USER_ID,
        email="deps2@test.com",
        hashed_password=hash_password("pw"),
    )
    db_session.add(user)
    await db_session.commit()

    mfa_token = create_mfa_token(str(TEST_USER_ID))
    resp = await anon_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {mfa_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_get_current_user_unknown_user_returns_404(
    anon_client: AsyncClient,
) -> None:
    from conftest import make_test_token

    token = make_test_token(uuid.UUID("00000000-0000-0000-0000-000000000099"))
    resp = await anon_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.unit
async def test_get_current_user_inactive_user_returns_400(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    from conftest import make_test_token

    inactive_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    user = User(
        id=inactive_id,
        email="inactive@test.com",
        hashed_password=hash_password("pw"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    token = make_test_token(inactive_id)
    resp = await anon_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_get_current_user_no_header_returns_403(
    anon_client: AsyncClient,
) -> None:
    resp = await anon_client.get("/api/v1/users/me")
    assert resp.status_code == 403


# ── get_mfa_pending_user (called directly) ─────────────────────────────────────


@pytest.mark.unit
async def test_get_mfa_pending_user_valid_token_returns_user(
    db_session: AsyncSession,
) -> None:
    from conftest import TEST_USER_ID, make_mfa_token

    user = User(
        id=TEST_USER_ID,
        email="mfadep@test.com",
        hashed_password=hash_password("pw"),
    )
    db_session.add(user)
    await db_session.commit()

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=make_mfa_token()
    )
    result = await get_mfa_pending_user(
        request=_FAKE_REQUEST, credentials=credentials, session=db_session
    )
    assert result.id == TEST_USER_ID


@pytest.mark.unit
async def test_get_mfa_pending_user_access_token_type_raises_401(
    db_session: AsyncSession,
) -> None:
    from conftest import make_test_token

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=make_test_token()
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_mfa_pending_user(
            request=_FAKE_REQUEST, credentials=credentials, session=db_session
        )
    assert exc_info.value.status_code == 401


@pytest.mark.unit
async def test_get_mfa_pending_user_bad_token_raises_401(
    db_session: AsyncSession,
) -> None:
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="garbage.token"
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_mfa_pending_user(
            request=_FAKE_REQUEST, credentials=credentials, session=db_session
        )
    assert exc_info.value.status_code == 401


@pytest.mark.unit
async def test_get_mfa_pending_user_unknown_user_raises_404(
    db_session: AsyncSession,
) -> None:
    from conftest import make_mfa_token

    unknown_id = uuid.UUID("00000000-0000-0000-0000-000000000088")
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=make_mfa_token(unknown_id)
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_mfa_pending_user(
            request=_FAKE_REQUEST, credentials=credentials, session=db_session
        )
    assert exc_info.value.status_code == 404


# ── get_mfa_user_id_from_token (called directly) ──────────────────────────────


@pytest.mark.unit
async def test_get_mfa_user_id_from_token_returns_uuid() -> None:
    from conftest import TEST_USER_ID, make_mfa_token

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=make_mfa_token()
    )
    result = await get_mfa_user_id_from_token(
        request=_FAKE_REQUEST, credentials=credentials
    )
    assert result == TEST_USER_ID


@pytest.mark.unit
async def test_get_mfa_user_id_from_token_access_type_raises_401() -> None:
    from conftest import make_test_token

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=make_test_token()
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_mfa_user_id_from_token(request=_FAKE_REQUEST, credentials=credentials)
    assert exc_info.value.status_code == 401


@pytest.mark.unit
async def test_get_mfa_user_id_from_token_bad_token_raises_401() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as exc_info:
        await get_mfa_user_id_from_token(request=_FAKE_REQUEST, credentials=credentials)
    assert exc_info.value.status_code == 401
