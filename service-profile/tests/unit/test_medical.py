"""Tests des routes médicales : blessures, pathologies, allergies, médicaments."""
import pytest
from httpx import AsyncClient


class TestMedicalRoutes:
    """Tests des endpoints de sécurité et données médicales."""

    @pytest.fixture(autouse=True)
    async def _create_profile(self, client: AsyncClient) -> None:
        """Crée un profil de base avant chaque test."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0})

    @pytest.mark.unit
    async def test_add_injury_nominal(self, client: AsyncClient) -> None:
        """Ajout d'une blessure retourne 201 avec slug."""
        resp = await client.post("/api/v1/profiles/me/injuries", json={
            "body_part": "Genou gauche", "injury_type": "Tendinite rotulienne",
        })
        assert resp.status_code == 201
        assert "slug" in resp.json()

    @pytest.mark.unit
    async def test_list_injuries_nominal(self, client: AsyncClient) -> None:
        """La liste des blessures contient bien l'élément ajouté."""
        await client.post("/api/v1/profiles/me/injuries", json={"body_part": "Dos", "injury_type": "Hernie"})
        resp = await client.get("/api/v1/profiles/me/injuries")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.unit
    async def test_delete_injury_nominal(self, client: AsyncClient) -> None:
        """Suppression d'une blessure par slug retourne 204."""
        created = await client.post("/api/v1/profiles/me/injuries", json={"body_part": "Cheville", "injury_type": "Entorse"})
        slug = created.json()["slug"]
        assert (await client.delete(f"/api/v1/profiles/me/injuries/{slug}")).status_code == 204

    @pytest.mark.unit
    async def test_add_condition_nominal(self, client: AsyncClient) -> None:
        """Ajout d'une pathologie retourne 201."""
        resp = await client.post("/api/v1/profiles/me/conditions", json={
            "category": "metabolic", "condition_name": "Diabète type 2",
        })
        assert resp.status_code == 201

    @pytest.mark.unit
    async def test_add_allergy_nominal(self, client: AsyncClient) -> None:
        """Ajout d'une allergie retourne 201 avec les champs corrects."""
        resp = await client.post("/api/v1/profiles/me/allergies", json={
            "allergen": "Lactose", "severity": "intolerance",
        })
        assert resp.status_code == 201
        assert resp.json()["allergen"] == "Lactose"
        assert resp.json()["severity"] == "intolerance"

    @pytest.mark.unit
    async def test_add_medication_nominal(self, client: AsyncClient) -> None:
        """Ajout d'un médicament avec impact métabolique retourne 201."""
        resp = await client.post("/api/v1/profiles/me/medications", json={
            "medication_name": "Statine 20mg", "impacts_metabolism": True,
        })
        assert resp.status_code == 201
        assert resp.json()["impacts_metabolism"] is True

    @pytest.mark.unit
    async def test_delete_allergy_not_found(self, client: AsyncClient) -> None:
        """Suppression d'une allergie inexistante retourne 404."""
        assert (await client.delete("/api/v1/profiles/me/allergies/ghost")).status_code == 404