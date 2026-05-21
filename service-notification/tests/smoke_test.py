import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_NOTIFICATION_URL = "http://localhost:8006"

_NOTIF_USER = {"email": "smoke_notification@test.internal", "password": "SmokeTest!99"}
_NULL_UUID = "00000000-0000-0000-0000-000000000000"

_FAKE_SUBSCRIPTION = {
    "endpoint": "https://smoke-test.example.com/push/device-smoke-abc",
    "p256dh_key": "BNcRdreALRFXTkOOUHK1EtK2wtWszOjke7gNF3GkBas6JfQ9GfSMWyUG4h1UEcYhPMzOVtAQzJOJhCQvGNgFqE8",
    "auth_key": "tBHItJI5svbpez7KI4CCXg",
    "device_label": "Smoke Test Device",
}


# ── Fixtures user / auth ─────────────────────────────────────────────────────────

@pytest.fixture()
def create_user():
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_NOTIF_USER)
        assert resp.status_code == 201, f"Création user échouée: {resp.text}"
        user = resp.json()
        user["password"] = _NOTIF_USER["password"]
        yield user
        login = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_NOTIF_USER)
        if login.status_code == 200:
            token = login.json()["access_token"]
            client.delete(
                f"{SERVICE_USER_URL}/api/v1/users/{user['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )


@pytest.fixture()
def auth_token(create_user):
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_NOTIF_USER)
        assert resp.status_code == 200
        return resp.json()["access_token"]


@pytest.fixture()
def user_id(create_user):
    return create_user["id"]


@pytest.fixture()
def subscription_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions",
            json=_FAKE_SUBSCRIPTION,
            headers=headers,
        )
        assert resp.status_code == 201, f"Création subscription échouée: {resp.text}"
        slug = resp.json()["slug"]
    yield slug
    with httpx.Client() as client:
        client.delete(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions/{slug}",
            headers=headers,
        )


# ── Health ───────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_notification_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_NOTIFICATION_URL}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "service-notification"


@pytest.mark.smoke
def test_notification_health_db():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_NOTIFICATION_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Subscriptions ────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_create_subscription(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {**_FAKE_SUBSCRIPTION, "endpoint": "https://smoke-create.example.com/push"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "slug" in body
        assert body["endpoint"] == payload["endpoint"]
        client.delete(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions/{body['slug']}",
            headers=headers,
        )


@pytest.mark.smoke
def test_create_subscription_idempotent(auth_token, subscription_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions",
            json=_FAKE_SUBSCRIPTION,
            headers=headers,
        )
    assert resp.status_code == 201
    assert resp.json()["slug"] == subscription_setup


@pytest.mark.smoke
def test_get_subscription_by_slug(auth_token, subscription_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions/{subscription_setup}",
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["slug"] == subscription_setup


@pytest.mark.smoke
def test_get_subscription_not_found(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions/slug-inexistant",
            headers=headers,
        )
    assert resp.status_code == 404


@pytest.mark.smoke
def test_delete_subscription(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {**_FAKE_SUBSCRIPTION, "endpoint": "https://smoke-delete.example.com/push"}
    with httpx.Client() as client:
        create = client.post(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions",
            json=payload,
            headers=headers,
        )
        assert create.status_code == 201
        slug = create.json()["slug"]
        delete = client.delete(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/subscriptions/{slug}",
            headers=headers,
        )
    assert delete.status_code == 204


# ── Historique notifications ──────────────────────────────────────────────────────

@pytest.mark.smoke
def test_history_empty_for_new_user(auth_token, user_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/users/{user_id}/history",
            headers=headers,
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 0


@pytest.mark.smoke
def test_history_pagination_params(auth_token, user_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/users/{user_id}/history",
            params={"limit": 10, "offset": 0},
            headers=headers,
        )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.smoke
def test_history_limit_too_high_rejected(auth_token, user_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/users/{user_id}/history",
            params={"limit": 300},
            headers=headers,
        )
    assert resp.status_code == 422


@pytest.mark.smoke
def test_history_forbidden_for_other_user(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_NOTIFICATION_URL}/api/v1/users/{_NULL_UUID}/history",
            headers=headers,
        )
    assert resp.status_code == 403