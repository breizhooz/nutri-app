"""End-to-end smoke tests for service-user — requires the full Docker stack."""

import httpx
import pyotp
import pytest

SERVICE_USER_URL = "http://localhost:8001"

_SMOKE_USER = {"email": "smoke_user@test.internal", "password": "SmokeTest!99"}
_SMOKE_MFA_USER = {"email": "smoke_mfa@test.internal", "password": "SmokeTest!99"}


@pytest.fixture()
def create_smoke_user():
    """Create and tear down a smoke test user."""
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_SMOKE_USER)
        assert resp.status_code == 201, f"Création user échouée: {resp.text}"
        user = resp.json()
        user["password"] = _SMOKE_USER["password"]
        yield user
        login = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_USER)
        if login.status_code == 200:
            token = login.json()["access_token"]
            client.delete(
                f"{SERVICE_USER_URL}/api/v1/users/{user['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )


@pytest.fixture()
def create_mfa_smoke_user():
    """Create and tear down a smoke test user with TOTP 2FA enabled."""
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_SMOKE_MFA_USER)
        assert resp.status_code == 201
        user = resp.json()

        login = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_MFA_USER)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/2fa/setup/totp", headers=headers
        )
        assert setup_resp.status_code == 200
        uri = setup_resp.json()["provisioning_uri"]

        import re
        secret_match = re.search(r"secret=([A-Z2-7]+)", uri)
        assert secret_match, "Could not parse TOTP secret from URI"
        secret = secret_match.group(1)

        code = pyotp.TOTP(secret).now()
        confirm = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/2fa/confirm/totp",
            json={"code": code},
            headers=headers,
        )
        assert confirm.status_code == 200, f"TOTP confirm failed: {confirm.text}"

        user["secret"] = secret
        yield user

        login2 = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_MFA_USER)
        if login2.status_code == 200:
            mfa_token = login2.json()["mfa_token"]
            code2 = pyotp.TOTP(secret).now()
            verify = client.post(
                f"{SERVICE_USER_URL}/api/v1/auth/2fa/verify",
                json={"mfa_token": mfa_token, "code": code2},
            )
            if verify.status_code == 200:
                access = verify.json()["access_token"]
                client.delete(
                    f"{SERVICE_USER_URL}/api/v1/users/{user['id']}",
                    headers={"Authorization": f"Bearer {access}"},
                )


# ── Health ────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_user_health() -> None:
    """Service liveness check returns ok."""
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_USER_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "service-user"


@pytest.mark.smoke
def test_user_health_db() -> None:
    """Database connectivity check returns ok."""
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_USER_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Users ─────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_create_user(create_smoke_user) -> None:
    """User creation returns id and correct email."""
    assert create_smoke_user["id"] is not None
    assert create_smoke_user["email"] == _SMOKE_USER["email"]


@pytest.mark.smoke
def test_create_user_duplicate(create_smoke_user) -> None:
    """Duplicate email registration returns 409."""
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_SMOKE_USER)
    assert response.status_code == 409


# ── Auth ──────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_login_returns_token(create_smoke_user) -> None:
    """Login without 2FA returns a non-empty access_token."""
    with httpx.Client() as client:
        response = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_USER
        )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["access_token"] != ""


@pytest.mark.smoke
def test_login_wrong_password(create_smoke_user) -> None:
    """Login with wrong password returns 401."""
    payload = {"email": _SMOKE_USER["email"], "password": "wrongpassword"}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
    assert response.status_code == 401


@pytest.mark.smoke
def test_login_unknown_user() -> None:
    """Login with unknown email returns 401."""
    payload = {"email": "nobody@unknown.internal", "password": "whatever"}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
    assert response.status_code == 401


# ── OAuth2 ────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_oauth_google_authorize_redirects() -> None:
    """GET /auth/oauth/google/authorize returns a redirect to Google."""
    with httpx.Client(follow_redirects=False) as client:
        resp = client.get(f"{SERVICE_USER_URL}/api/v1/auth/oauth/google/authorize")
    assert resp.status_code == 302
    assert "accounts.google.com" in resp.headers.get("location", "")


@pytest.mark.smoke
def test_oauth_facebook_authorize_redirects() -> None:
    """GET /auth/oauth/facebook/authorize returns a redirect to Facebook."""
    with httpx.Client(follow_redirects=False) as client:
        resp = client.get(f"{SERVICE_USER_URL}/api/v1/auth/oauth/facebook/authorize")
    assert resp.status_code == 302
    assert "facebook.com" in resp.headers.get("location", "")


@pytest.mark.smoke
def test_oauth_unknown_provider_returns_400() -> None:
    """Unknown provider returns 400."""
    with httpx.Client(follow_redirects=False) as client:
        resp = client.get(f"{SERVICE_USER_URL}/api/v1/auth/oauth/twitter/authorize")
    assert resp.status_code == 400


# ── 2FA TOTP ──────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_totp_login_flow(create_mfa_smoke_user) -> None:
    """Full TOTP login flow: login → mfa_token → verify → access_token."""
    secret = create_mfa_smoke_user["secret"]
    with httpx.Client() as client:
        login_resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_MFA_USER
        )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert "mfa_token" in body
    assert body["mfa_method"] == "totp"

    mfa_token = body["mfa_token"]
    code = pyotp.TOTP(secret).now()
    with httpx.Client() as client:
        verify_resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/2fa/verify",
            json={"mfa_token": mfa_token, "code": code},
        )
    assert verify_resp.status_code == 200
    assert "access_token" in verify_resp.json()


@pytest.mark.smoke
def test_totp_wrong_code_rejected(create_mfa_smoke_user) -> None:
    """Wrong TOTP code at verify step returns 400."""
    with httpx.Client() as client:
        login_resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_MFA_USER
        )
    mfa_token = login_resp.json()["mfa_token"]
    with httpx.Client() as client:
        verify_resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/2fa/verify",
            json={"mfa_token": mfa_token, "code": "000000"},
        )
    assert verify_resp.status_code == 400