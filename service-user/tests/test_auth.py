"""Tests for /auth/login and /auth/refresh endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token, hash_password
from app.models.user import User
from app.services.crypto_service import CryptoService
from app.services.totp_service import TotpService


async def _create_user(
    session: AsyncSession,
    email: str = "auth@test.com",
    password: str = "password123",
    two_factor_enabled: bool = False,
    two_factor_method: str | None = None,
    totp_secret_plain: str | None = None,
) -> User:
    """Helper: insert a user directly into the test DB."""
    from app.core.config import settings

    user = User(
        email=email,
        hashed_password=hash_password(password),
        two_factor_enabled=two_factor_enabled,
        two_factor_method=two_factor_method,
    )
    if totp_secret_plain:
        user.totp_secret = CryptoService.encrypt(
            totp_secret_plain, settings.MFA_TOTP_ENCRYPTION_KEY
        )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.unit
async def test_login_no_2fa_returns_access_and_refresh_cookie(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login without 2FA returns the access token in body, refresh in HttpOnly cookie."""
    await _create_user(db_session)
    resp = await anon_client.post(
        "/api/v1/auth/login", json={"email": "auth@test.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    # SEC-05: refresh never returned in the JSON body anymore.
    assert "refresh_token" not in body
    assert body["token_type"] == "Bearer"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie


@pytest.mark.unit
async def test_login_wrong_password_returns_401(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login with wrong password returns 401."""
    await _create_user(db_session)
    resp = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "auth@test.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_login_unknown_email_returns_401(anon_client: AsyncClient) -> None:
    """Login with unknown email returns 401."""
    resp = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "password123"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_login_inactive_user_returns_400(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login with inactive account returns 400."""
    user = await _create_user(db_session)
    user.is_active = False
    session = db_session
    session.add(user)
    await session.commit()
    resp = await anon_client.post(
        "/api/v1/auth/login", json={"email": "auth@test.com", "password": "password123"}
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_login_totp_enabled_returns_mfa_token(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login with TOTP-enabled account returns mfa_token instead of full tokens."""
    secret = TotpService.generate_secret()
    await _create_user(
        db_session,
        two_factor_enabled=True,
        two_factor_method="totp",
        totp_secret_plain=secret,
    )
    resp = await anon_client.post(
        "/api/v1/auth/login", json={"email": "auth@test.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "mfa_token" in body
    assert body["mfa_method"] == "totp"
    assert "access_token" not in body


@pytest.mark.unit
async def test_login_oauth_only_user_no_password_returns_401(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login with email+password for an OAuth-only account (no password) returns 401."""
    user = User(email="oauth@test.com", hashed_password=None)
    db_session.add(user)
    await db_session.commit()
    resp = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "oauth@test.com", "password": "password123"},
    )
    assert resp.status_code == 401


@pytest.mark.unit
async def test_refresh_valid_cookie(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A valid refresh cookie returns a fresh access token and rotates the cookie."""
    user = await _create_user(db_session)
    refresh = create_refresh_token(str(user.id))
    anon_client.cookies.set("refresh_token", refresh)
    resp = await anon_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body
    # Rotation: a new refresh cookie is issued on every refresh.
    assert "refresh_token=" in resp.headers.get("set-cookie", "")


@pytest.mark.unit
async def test_refresh_invalid_cookie_returns_401(anon_client: AsyncClient) -> None:
    """An invalid refresh cookie returns 401."""
    anon_client.cookies.set("refresh_token", "not.a.token")
    resp = await anon_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.unit
async def test_refresh_missing_cookie_returns_401(anon_client: AsyncClient) -> None:
    """No refresh cookie at all returns 401."""
    resp = await anon_client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.unit
async def test_logout_clears_refresh_cookie(anon_client: AsyncClient) -> None:
    """Logout returns 204 and emits a Set-Cookie clearing the refresh token."""
    resp = await anon_client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
