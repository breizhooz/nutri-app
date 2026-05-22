import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_NUTRITION_URL = "http://localhost:8005"

_NUTRITION_USER = {"email": "smoke_nutrition@test.internal", "password": "SmokeTest!99"}
_NULL_UUID = "00000000-0000-0000-0000-000000000000"


# ── Fixtures user / auth ─────────────────────────────────────────────────────────


@pytest.fixture()
def create_user():
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_NUTRITION_USER)
        assert resp.status_code == 201, f"Création user échouée: {resp.text}"
        user = resp.json()
        user["password"] = _NUTRITION_USER["password"]
        yield user
        login = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/login", json=_NUTRITION_USER
        )
        if login.status_code == 200:
            token = login.json()["access_token"]
            client.delete(
                f"{SERVICE_USER_URL}/api/v1/users/{user['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )


@pytest.fixture()
def auth_token(create_user):
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_USER_URL}/api/v1/auth/login", json=_NUTRITION_USER
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]


@pytest.fixture()
def user_id(create_user):
    return create_user["id"]


# ── Health ───────────────────────────────────────────────────────────────────────
# Note : service-nutrition ne renvoie PAS de champ "service" dans /health


@pytest.mark.smoke
def test_nutrition_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_NUTRITION_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── Nutrition items (public) ─────────────────────────────────────────────────────


@pytest.mark.smoke
def test_get_nutrition_item_not_found():
    with httpx.Client() as client:
        response = client.get(
            f"{SERVICE_NUTRITION_URL}/api/v1/nutrition-items/slug-inexistant"
        )
    assert response.status_code == 404


@pytest.mark.smoke
def test_update_nutrition_item_not_found(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.patch(
            f"{SERVICE_NUTRITION_URL}/api/v1/nutrition-items/slug-inexistant",
            json={"calories": 200.0},
            headers=headers,
        )
    assert response.status_code == 404


# ── Macro errors ─────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_macro_errors_empty_for_new_user(auth_token, user_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(
            f"{SERVICE_NUTRITION_URL}/api/v1/users/{user_id}/macro-errors",
            headers=headers,
        )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0


@pytest.mark.smoke
def test_macro_errors_forbidden_for_other_user(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(
            f"{SERVICE_NUTRITION_URL}/api/v1/users/{_NULL_UUID}/macro-errors",
            headers=headers,
        )
    assert response.status_code == 403


@pytest.mark.smoke
def test_resolve_macro_error_not_found(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.patch(
            f"{SERVICE_NUTRITION_URL}/api/v1/macro-errors/slug-inexistant",
            json={"resolved_name": "Poulet rôti"},
            headers=headers,
        )
    assert response.status_code == 404


# ── Stats ────────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_stats_empty_for_new_user(auth_token, user_id):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(
            f"{SERVICE_NUTRITION_URL}/api/v1/users/{user_id}/stats",
            headers=headers,
        )
    assert response.status_code == 200
    body = response.json()
    assert "recipes_analysed" in body
    assert "macro_errors_pending" in body
    assert "macro_errors_resolved" in body
    assert "avg_daily" in body
    assert body["recipes_analysed"] == 0
    assert body["macro_errors_pending"] == 0
    assert body["macro_errors_resolved"] == 0


@pytest.mark.smoke
def test_stats_forbidden_for_other_user(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(
            f"{SERVICE_NUTRITION_URL}/api/v1/users/{_NULL_UUID}/stats",
            headers=headers,
        )
    assert response.status_code == 403
