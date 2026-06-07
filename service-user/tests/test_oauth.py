"""Tests for /auth/oauth/{provider}/* endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.oauth_account import OAuthAccount
from app.models.user import User


@pytest.mark.unit
async def test_authorize_google_redirects(anon_client: AsyncClient) -> None:
    """GET /auth/oauth/google/authorize returns a 302 redirect."""
    resp = await anon_client.get(
        "/api/v1/auth/oauth/google/authorize", follow_redirects=False
    )
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers["location"]


@pytest.mark.unit
async def test_authorize_facebook_redirects(anon_client: AsyncClient) -> None:
    """GET /auth/oauth/facebook/authorize returns a 302 redirect."""
    resp = await anon_client.get(
        "/api/v1/auth/oauth/facebook/authorize", follow_redirects=False
    )
    assert resp.status_code == 302
    assert "facebook.com" in resp.headers["location"]


@pytest.mark.unit
async def test_authorize_unknown_provider_returns_400(anon_client: AsyncClient) -> None:
    """Unknown provider returns 400."""
    resp = await anon_client.get(
        "/api/v1/auth/oauth/twitter/authorize", follow_redirects=False
    )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_callback_invalid_state_redirects_with_error(
    anon_client: AsyncClient,
) -> None:
    """Callback with bad state JWT redirects to the front with an error (SEC-05)."""
    resp = await anon_client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "auth-code", "state": "invalid-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/oauth/callback?error=" in resp.headers["location"]


@pytest.mark.unit
async def test_callback_unknown_provider_redirects_with_error(
    anon_client: AsyncClient,
) -> None:
    """Callback for unknown provider redirects to the front with an error."""
    from app.core.security import create_oauth_state

    state = create_oauth_state("twitter")
    resp = await anon_client.get(
        "/api/v1/auth/oauth/twitter/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/oauth/callback?error=" in resp.headers["location"]


@pytest.mark.unit
async def test_callback_creates_new_user_and_sets_cookie(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """New user: account created, refresh cookie set, redirect carries no token (SEC-05)."""
    from app.core.security import create_oauth_state

    state = create_oauth_state("google")

    with (
        patch(
            "app.api.routes.oauth.OAuthService.exchange_code",
            new=AsyncMock(return_value={"access_token": "fake-at"}),
        ),
        patch(
            "app.api.routes.oauth.OAuthService.fetch_user_info",
            new=AsyncMock(
                return_value={"sub": "google-uid-123", "email": "new@oauth.com"}
            ),
        ),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/oauth/callback")  # no token leaked
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie


@pytest.mark.unit
async def test_callback_2fa_user_redirects_with_mfa_token(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A 2FA-enabled user is redirected with an mfa_token, no refresh cookie yet."""
    from app.core.security import create_oauth_state

    user = User(
        email="2fa@oauth.com",
        hashed_password=None,
        two_factor_enabled=True,
        two_factor_method="totp",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google-uid-2fa",
            provider_email="2fa@oauth.com",
        )
    )
    await db_session.commit()

    state = create_oauth_state("google")
    with (
        patch(
            "app.api.routes.oauth.OAuthService.exchange_code",
            new=AsyncMock(return_value={"access_token": "fake-at"}),
        ),
        patch(
            "app.api.routes.oauth.OAuthService.fetch_user_info",
            new=AsyncMock(
                return_value={"sub": "google-uid-2fa", "email": "2fa@oauth.com"}
            ),
        ),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "mfa_token=" in resp.headers["location"]
    assert "refresh_token=" not in resp.headers.get("set-cookie", "")


@pytest.mark.unit
async def test_callback_links_existing_user_by_email(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Callback for email matching an existing user links the OAuth account."""
    from app.core.security import create_oauth_state
    from sqlalchemy import select

    existing_user = User(
        email="existing@oauth.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(existing_user)
    await db_session.commit()

    state = create_oauth_state("google")

    with (
        patch(
            "app.api.routes.oauth.OAuthService.exchange_code",
            new=AsyncMock(return_value={"access_token": "fake-at"}),
        ),
        patch(
            "app.api.routes.oauth.OAuthService.fetch_user_info",
            new=AsyncMock(
                return_value={"sub": "google-uid-456", "email": "existing@oauth.com"}
            ),
        ),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    result = await db_session.execute(
        select(OAuthAccount).where(OAuthAccount.provider == "google")
    )
    link = result.scalar_one_or_none()
    assert link is not None
    assert link.user_id == existing_user.id


@pytest.mark.unit
async def test_callback_provider_failure_redirects_with_error(
    anon_client: AsyncClient,
) -> None:
    """Callback where exchange_code raises redirects to the front with an error."""
    from app.core.security import create_oauth_state

    state = create_oauth_state("google")
    with patch(
        "app.api.routes.oauth.OAuthService.exchange_code",
        new=AsyncMock(side_effect=Exception("provider down")),
    ):
        resp = await anon_client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "/oauth/callback?error=" in resp.headers["location"]


@pytest.mark.unit
async def test_callback_state_provider_mismatch_redirects_with_error(
    anon_client: AsyncClient,
) -> None:
    """State token for google but callback on facebook redirects with an error."""
    from app.core.security import create_oauth_state

    state = create_oauth_state("google")
    resp = await anon_client.get(
        "/api/v1/auth/oauth/facebook/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/oauth/callback?error=" in resp.headers["location"]
