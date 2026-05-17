import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"

_SMOKE_USER = {"email": "smoke_user@test.internal", "password": "SmokeTest!99"}


@pytest.fixture()
def create_smoke_user():
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


# ── Health ──────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_user_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_USER_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "service-user"


@pytest.mark.smoke
def test_user_health_db():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_USER_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Utilisateurs ────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_create_user(create_smoke_user):
    assert create_smoke_user["id"] is not None
    assert create_smoke_user["email"] == _SMOKE_USER["email"]


@pytest.mark.smoke
def test_create_user_duplicate(create_smoke_user):
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_SMOKE_USER)
    assert response.status_code == 409


# ── Auth ────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_login_returns_token(create_smoke_user):
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_SMOKE_USER)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["access_token"] != ""


@pytest.mark.smoke
def test_login_wrong_password(create_smoke_user):
    payload = {"email": _SMOKE_USER["email"], "password": "wrongpassword"}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
    assert response.status_code in (401, 403)


@pytest.mark.smoke
def test_login_unknown_user():
    payload = {"email": "nobody@unknown.internal", "password": "whatever"}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
    assert response.status_code in (401, 404)
