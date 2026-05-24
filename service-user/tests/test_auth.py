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
async def test_login_no_2fa_returns_token_pair(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Login without 2FA returns access and refresh tokens immediately."""
    await _create_user(db_session)
    resp = await anon_client.post(
        "/api/v1/auth/login", json={"email": "auth@test.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "Bearer"


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
async def test_refresh_valid_token(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Valid refresh token returns a new token pair."""
    user = await _create_user(db_session)
    refresh = create_refresh_token(str(user.id))
    resp = await anon_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.unit
async def test_refresh_invalid_token_returns_401(anon_client: AsyncClient) -> None:
    """Invalid refresh token returns 401."""
    resp = await anon_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not.a.token"}
    )
    assert resp.status_code == 401
