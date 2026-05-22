"""Tests des routes du profil principal."""

import uuid
import pytest
from httpx import AsyncClient


class TestProfileRoutes:
    """Tests des endpoints CRUD et calcul du profil."""

    @pytest.mark.unit
    async def test_create_profile_nominal(self, client: AsyncClient) -> None:
        """Création d'un profil retourne 201 avec slug et données correctes."""
        resp = await client.post(
            "/api/v1/profiles",
            json={
                "date_of_birth": "1992-03-15",
                "biological_sex": "male",
                "height_cm": 181.0,
                "weight_kg": 88.5,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["biological_sex"] == "male"
        assert body["slug"].startswith("profile-")
        assert body["weight_kg"] == pytest.approx(88.5, abs=0.01)

    @pytest.mark.unit
    async def test_create_profile_duplicate_returns_409(
        self, client: AsyncClient
    ) -> None:
        """Deuxième création pour le même utilisateur retourne 409."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        resp = await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        assert resp.status_code == 409

    @pytest.mark.unit
    async def test_get_my_profile_nominal(self, client: AsyncClient) -> None:
        """GET /me retourne le profil créé."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        resp = await client.get("/api/v1/profiles/me")
        assert resp.status_code == 200
        assert "slug" in resp.json()

    @pytest.mark.unit
    async def test_get_my_profile_not_found(self, client: AsyncClient) -> None:
        """GET /me retourne 404 si aucun profil n'existe."""
        resp = await client.get("/api/v1/profiles/me")
        assert resp.status_code == 404

    @pytest.mark.unit
    async def test_update_profile_nominal(self, client: AsyncClient) -> None:
        """PATCH /me met à jour les champs fournis."""
        await client.post("/api/v1/profiles", json={"weight_kg": 90.0})
        resp = await client.patch("/api/v1/profiles/me", json={"weight_kg": 85.0})
        assert resp.status_code == 200
        assert resp.json()["weight_kg"] == pytest.approx(85.0, abs=0.01)

    @pytest.mark.unit
    async def test_calculate_missing_data_returns_422(
        self, client: AsyncClient
    ) -> None:
        """Calcul sans données anthropométriques retourne 422."""
        await client.post("/api/v1/profiles", json={})
        resp = await client.get("/api/v1/profiles/me/calculate")
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_calculate_full_returns_metrics(self, client: AsyncClient) -> None:
        """Calcul complet retourne IMC, MB et TDEE cohérents."""
        await client.post(
            "/api/v1/profiles",
            json={
                "date_of_birth": "1992-03-15",
                "biological_sex": "male",
                "height_cm": 181.0,
                "weight_kg": 88.5,
            },
        )
        resp = await client.get("/api/v1/profiles/me/calculate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["bmi"] == pytest.approx(27.0, abs=0.5)
        assert body["bmr_kcal"] > 1500
        assert body["tdee_kcal"] >= body["bmr_kcal"]

    @pytest.mark.unit
    async def test_inter_service_endpoint(
        self, client: AsyncClient, service_client: AsyncClient, test_user_id: uuid.UUID
    ) -> None:
        """L'endpoint inter-service retourne le profil avec le token de service."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        resp = await service_client.get(f"/api/v1/profiles/{test_user_id}")
        assert resp.status_code == 200

    @pytest.mark.unit
    async def test_inter_service_rejected_without_token(
        self, client: AsyncClient, test_user_id: uuid.UUID
    ) -> None:
        """L'endpoint inter-service retourne 403 avec un token utilisateur."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})
        resp = await client.get(f"/api/v1/profiles/{test_user_id}")
        assert resp.status_code == 403
