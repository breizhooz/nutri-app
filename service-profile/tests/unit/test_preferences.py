"""Tests des routes de personnalisation : sports, performances, lifestyle, nutrition."""
import pytest
from httpx import AsyncClient


_SPORTS_PAYLOAD: dict = {
    "sports": ["Musculation", "Course à pied"],
    "practice_level": "intermediate",
    "sessions_per_week": 4,
    "avg_session_duration_min": 60,
    "avg_intensity_rpe": 7,
}

_PROFILE_PAYLOAD: dict = {
    "date_of_birth": "1990-05-15",
    "biological_sex": "male",
    "height_cm": 178.0,
    "weight_kg": 80.0,
}

class TestPreferencesRoutes:
    """Tests des endpoints de personnalisation du profil."""

    @pytest.fixture(autouse=True)
    async def _create_profile(self, client: AsyncClient) -> None:
        """Crée un profil de base avant chaque test."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})

    @pytest.mark.unit
    async def test_upsert_sports_create(self, client: AsyncClient) -> None:
        """Premier PUT crée le profil sportif et retourne 200."""
        resp = await client.put("/api/v1/profiles/me/sports", json=_SPORTS_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["sessions_per_week"] == 4

    @pytest.mark.unit
    async def test_upsert_sports_update(self, client: AsyncClient) -> None:
        """Deuxième PUT met à jour le profil sportif existant."""
        await client.put("/api/v1/profiles/me/sports", json=_SPORTS_PAYLOAD)
        updated = {**_SPORTS_PAYLOAD, "sessions_per_week": 5}
        resp = await client.put("/api/v1/profiles/me/sports", json=updated)
        assert resp.status_code == 200
        assert resp.json()["sessions_per_week"] == 5

    @pytest.mark.unit
    async def test_get_sports_not_found(self, client: AsyncClient) -> None:
        """GET /sports sans profil renvoie 404."""
        resp = await client.get("/api/v1/profiles/me/sports")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_sports_found(self, client: AsyncClient) -> None:
        """GET /sports renvoie le profil sportif créé."""
        await client.put("/api/v1/profiles/me/sports", json=_SPORTS_PAYLOAD)
        resp = await client.get("/api/v1/profiles/me/sports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions_per_week"] == _SPORTS_PAYLOAD["sessions_per_week"]


_LIFESTYLE_PAYLOAD: dict = {
    "stress_level": "moderate",
    "sleep_hours": 7.5,
    "chronotype": "intermediate",
    "alcohol_frequency": "never",
    "is_smoker": False,
    "sedentary_hours_per_day": 6.0,
}

_NUTRITION_PAYLOAD: dict = {
    "diet_type": "omnivore",
    "main_goal": "maintenance",
    "cooking_level": "intermediate",
    "cooking_time": "medium",
    "cooking_for": "couple",
    "budget_per_day_eur": 15.0,
    "excluded_foods": ["shellfish", "offal"],
}


@pytest.mark.asyncio
class TestLifestyleRoutes:
    """Tests des routes PUT/GET lifestyle."""

    @pytest.fixture(autouse=True)
    async def setup(self, client: AsyncClient) -> None:
        """Crée un profil de base avant chaque test de cette classe."""
        await client.post("/api/v1/profiles", json=_PROFILE_PAYLOAD)

    @pytest.mark.unit
    async def test_upsert_lifestyle_create(self, client: AsyncClient) -> None:
        """PUT /lifestyle crée le profil lifestyle."""
        resp = await client.put("/api/v1/profiles/me/lifestyle", json=_LIFESTYLE_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stress_level"] == "moderate"
        assert data["sleep_hours"] == 7.5
        assert data["is_smoker"] is False

    @pytest.mark.unit
    async def test_upsert_lifestyle_update(self, client: AsyncClient) -> None:
        """Deuxième PUT met à jour le profil lifestyle."""
        await client.put("/api/v1/profiles/me/lifestyle", json=_LIFESTYLE_PAYLOAD)
        updated = {**_LIFESTYLE_PAYLOAD, "sleep_hours": 8.0}
        resp = await client.put("/api/v1/profiles/me/lifestyle", json=updated)
        assert resp.status_code == 200
        assert resp.json()["sleep_hours"] == 8.0

    @pytest.mark.unit
    async def test_get_lifestyle_not_found(self, client: AsyncClient) -> None:
        """GET /lifestyle sans profil lifestyle renvoie 404."""
        resp = await client.get("/api/v1/profiles/me/lifestyle")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_lifestyle_found(self, client: AsyncClient) -> None:
        """GET /lifestyle renvoie le profil lifestyle créé."""
        await client.put("/api/v1/profiles/me/lifestyle", json=_LIFESTYLE_PAYLOAD)
        resp = await client.get("/api/v1/profiles/me/lifestyle")
        assert resp.status_code == 200
        assert resp.json()["chronotype"] == "intermediate"


@pytest.mark.asyncio
class TestNutritionRoutes:
    """Tests des routes PUT/GET nutrition preferences."""

    @pytest.fixture(autouse=True)
    async def setup(self, client: AsyncClient) -> None:
        """Crée un profil de base avant chaque test."""
        await client.post("/api/v1/profiles", json=_PROFILE_PAYLOAD)

    @pytest.mark.unit
    async def test_upsert_nutrition_create(self, client: AsyncClient) -> None:
        """PUT /nutrition crée les préférences nutritionnelles."""
        resp = await client.put("/api/v1/profiles/me/nutrition", json=_NUTRITION_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["diet_type"] == "omnivore"
        assert data["main_goal"] == "maintenance"
        assert "shellfish" in data["excluded_foods"]

    @pytest.mark.unit
    async def test_upsert_nutrition_update(self, client: AsyncClient) -> None:
        """Deuxième PUT met à jour les préférences nutritionnelles."""
        await client.put("/api/v1/profiles/me/nutrition", json=_NUTRITION_PAYLOAD)
        updated = {**_NUTRITION_PAYLOAD, "budget_per_day_eur": 20.0}
        resp = await client.put("/api/v1/profiles/me/nutrition", json=updated)
        assert resp.status_code == 200
        assert resp.json()["budget_per_day_eur"] == 20.0

    @pytest.mark.unit
    async def test_get_nutrition_not_found(self, client: AsyncClient) -> None:
        """GET /nutrition sans préférences renvoie 404."""
        resp = await client.get("/api/v1/profiles/me/nutrition")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_get_nutrition_found(self, client: AsyncClient) -> None:
        """GET /nutrition renvoie les préférences créées."""
        await client.put("/api/v1/profiles/me/nutrition", json=_NUTRITION_PAYLOAD)
        resp = await client.get("/api/v1/profiles/me/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cooking_level"] == "intermediate"
        assert data["cooking_for"] == "couple"