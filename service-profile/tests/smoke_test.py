import pytest
import httpx

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_PROFILE_URL = "http://localhost:8007"

_PROFILE_USER = {"email": "smoke_profile@test.internal", "password": "SmokeTest!99"}

_FULL_PROFILE = {
    "date_of_birth": "1990-06-15",
    "biological_sex": "male",
    "height_cm": 178.0,
    "weight_kg": 80.0,
    "target_weight_kg": 75.0,
}


# ── Fixtures user / auth ─────────────────────────────────────────────────────────


@pytest.fixture()
def create_user():
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=_PROFILE_USER)
        assert resp.status_code == 201, f"Création user échouée: {resp.text}"
        user = resp.json()
        user["password"] = _PROFILE_USER["password"]
        yield user
        login = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_PROFILE_USER)
        if login.status_code == 200:
            token = login.json()["access_token"]
            client.delete(
                f"{SERVICE_USER_URL}/api/v1/users/{user['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )


@pytest.fixture()
def auth_token(create_user):
    with httpx.Client() as client:
        resp = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=_PROFILE_USER)
        assert resp.status_code == 200
        return resp.json()["access_token"]


@pytest.fixture()
def profile_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles",
            json=_FULL_PROFILE,
            headers=headers,
        )
        assert resp.status_code == 201, f"Erreur création profil: {resp.text}"
        yield resp.json()


# ── Health ───────────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_profile_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_PROFILE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "service-profile"


@pytest.mark.smoke
def test_profile_health_db():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_PROFILE_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Profil CRUD ──────────────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_create_profile(profile_setup):
    assert profile_setup["id"] is not None
    assert profile_setup["biological_sex"] == "male"
    assert profile_setup["height_cm"] == pytest.approx(178.0, abs=0.01)


@pytest.mark.smoke
def test_create_profile_duplicate_returns_409(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles",
            json=_FULL_PROFILE,
            headers=headers,
        )
    assert resp.status_code == 409


@pytest.mark.smoke
def test_get_profile_me(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(f"{SERVICE_PROFILE_URL}/api/v1/profiles/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == profile_setup["id"]


@pytest.mark.smoke
def test_get_profile_me_not_found(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(f"{SERVICE_PROFILE_URL}/api/v1/profiles/me", headers=headers)
    assert resp.status_code == 404


@pytest.mark.smoke
def test_update_profile(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.patch(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me",
            json={"weight_kg": 79.0},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == pytest.approx(79.0, abs=0.01)


@pytest.mark.smoke
def test_calculate_profile_full(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/calculate", headers=headers
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bmi"] > 0
    assert body["bmr_kcal"] > 1000
    assert body["tdee_kcal"] >= body["bmr_kcal"]
    assert "ideal_weight_min_kg" in body
    assert "ideal_weight_max_kg" in body


@pytest.mark.smoke
def test_calculate_profile_no_data_returns_422(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        client.post(f"{SERVICE_PROFILE_URL}/api/v1/profiles", json={}, headers=headers)
        resp = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/calculate", headers=headers
        )
    assert resp.status_code == 422


# ── Médical : blessures ──────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_injury_lifecycle(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        create = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/injuries",
            json={"body_part": "Genou gauche", "injury_type": "Tendinite rotulienne"},
            headers=headers,
        )
        assert create.status_code == 201
        slug = create.json()["slug"]

        lst = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/injuries", headers=headers
        )
        assert lst.status_code == 200
        assert any(i["slug"] == slug for i in lst.json())

        delete = client.delete(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/injuries/{slug}",
            headers=headers,
        )
        assert delete.status_code == 204


# ── Médical : allergies ──────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_allergy_lifecycle(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        create = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/allergies",
            json={"allergen": "Gluten", "severity": "intolerance"},
            headers=headers,
        )
        assert create.status_code == 201
        assert create.json()["allergen"] == "Gluten"
        slug = create.json()["slug"]

        lst = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/allergies", headers=headers
        )
        assert lst.status_code == 200
        assert any(a["slug"] == slug for a in lst.json())

        delete = client.delete(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/allergies/{slug}",
            headers=headers,
        )
        assert delete.status_code == 204


# ── Médical : pathologies & médicaments ──────────────────────────────────────────


@pytest.mark.smoke
def test_add_medical_condition(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/conditions",
            json={"category": "metabolic", "condition_name": "Diabète type 2"},
            headers=headers,
        )
    assert resp.status_code == 201
    assert resp.json()["condition_name"] == "Diabète type 2"


@pytest.mark.smoke
def test_add_medication(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/medications",
            json={"medication_name": "Metformine 500mg", "impacts_metabolism": True},
            headers=headers,
        )
    assert resp.status_code == 201
    assert resp.json()["impacts_metabolism"] is True


# ── Tracker : composition corporelle ─────────────────────────────────────────────


@pytest.mark.smoke
def test_body_composition_lifecycle(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        create = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/composition",
            json={
                "measured_at": "2026-05-21",
                "body_fat_percentage": 18.5,
                "lean_mass_kg": 65.2,
            },
            headers=headers,
        )
        assert create.status_code == 201
        slug = create.json()["slug"]

        lst = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/composition", headers=headers
        )
        assert lst.status_code == 200
        assert any(c["slug"] == slug for c in lst.json())

        delete = client.delete(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/composition/{slug}",
            headers=headers,
        )
        assert delete.status_code == 204


# ── Tracker : mensurations ────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_body_measurements_lifecycle(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        create = client.post(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/measurements",
            json={"measured_at": "2026-05-21", "waist_cm": 82.0, "hips_cm": 98.0},
            headers=headers,
        )
        assert create.status_code == 201
        slug = create.json()["slug"]

        lst = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/measurements", headers=headers
        )
        assert lst.status_code == 200
        assert any(m["slug"] == slug for m in lst.json())

        delete = client.delete(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/measurements/{slug}",
            headers=headers,
        )
        assert delete.status_code == 204


# ── Préférences : sport ──────────────────────────────────────────────────────────


@pytest.mark.smoke
def test_sports_profile_lifecycle(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "sports": ["Musculation", "Course à pied"],
        "practice_level": "intermediate",
        "sessions_per_week": 4,
        "avg_session_duration_min": 60,
        "avg_intensity_rpe": 7,
    }
    with httpx.Client() as client:
        put = client.put(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/sports",
            json=payload,
            headers=headers,
        )
        assert put.status_code == 200
        assert put.json()["sessions_per_week"] == 4

        get = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/sports", headers=headers
        )
        assert get.status_code == 200
        assert get.json()["sessions_per_week"] == 4


@pytest.mark.smoke
def test_get_sports_not_found_without_setup(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        resp = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/sports", headers=headers
        )
    assert resp.status_code == 404


# ── Préférences : lifestyle ──────────────────────────────────────────────────────


@pytest.mark.smoke
def test_lifestyle_upsert(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "sleep_hours": 7.5,
        "stress_level": "moderate",
        "is_smoker": False,
        "sedentary_hours_per_day": 8.0,
    }
    with httpx.Client() as client:
        put = client.put(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/lifestyle",
            json=payload,
            headers=headers,
        )
        assert put.status_code == 200
        assert put.json()["sleep_hours"] == pytest.approx(7.5, abs=0.01)

        get = client.get(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/lifestyle", headers=headers
        )
        assert get.status_code == 200


# ── Préférences : nutrition ──────────────────────────────────────────────────────


@pytest.mark.smoke
def test_nutrition_preferences_upsert(auth_token, profile_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "diet_type": "omnivore",
        "main_goal": "weight_loss",
        "meals_per_day": 3,
        "supplements": [],
        "excluded_foods": [],
    }
    with httpx.Client() as client:
        put = client.put(
            f"{SERVICE_PROFILE_URL}/api/v1/profiles/me/nutrition",
            json=payload,
            headers=headers,
        )
        assert put.status_code == 200
        assert put.json()["diet_type"] == "omnivore"
