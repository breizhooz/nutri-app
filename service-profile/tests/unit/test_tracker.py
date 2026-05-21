"""Tests des routes de suivi corporel."""
import pytest
from httpx import AsyncClient


class TestTrackerRoutes:
    """Tests des endpoints de composition corporelle et de mensurations."""

    @pytest.fixture(autouse=True)
    async def _create_profile(self, client: AsyncClient) -> None:
        """Crée un profil de base avant chaque test."""
        await client.post("/api/v1/profiles", json={"height_cm": 175.0, "weight_kg": 70.0})

    @pytest.mark.unit
    async def test_add_composition_nominal(self, client: AsyncClient) -> None:
        """Ajout d'un snapshot de composition retourne 201."""
        resp = await client.post("/api/v1/profiles/me/composition", json={
            "measured_at": "2026-05-01", "body_fat_percentage": 19.2, "lean_mass_kg": 56.6,
        })
        assert resp.status_code == 201
        assert resp.json()["body_fat_percentage"] == pytest.approx(19.2, abs=0.01)

    @pytest.mark.unit
    async def test_list_composition_ordered_desc(self, client: AsyncClient) -> None:
        """L'historique est retourné du plus récent au plus ancien."""
        await client.post("/api/v1/profiles/me/composition", json={"measured_at": "2026-04-01"})
        await client.post("/api/v1/profiles/me/composition", json={"measured_at": "2026-05-01"})
        resp = await client.get("/api/v1/profiles/me/composition")
        assert resp.status_code == 200
        dates = [item["measured_at"] for item in resp.json()]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.unit
    async def test_delete_composition_nominal(self, client: AsyncClient) -> None:
        """Suppression d'un snapshot existant retourne 204."""
        created = await client.post("/api/v1/profiles/me/composition", json={"measured_at": "2026-05-01"})
        slug = created.json()["slug"]
        assert (await client.delete(f"/api/v1/profiles/me/composition/{slug}")).status_code == 204

    @pytest.mark.unit
    async def test_delete_composition_not_found(self, client: AsyncClient) -> None:
        """Suppression d'un slug inexistant retourne 404."""
        assert (await client.delete("/api/v1/profiles/me/composition/ghost-slug")).status_code == 404

    @pytest.mark.unit
    async def test_add_measurements_nominal(self, client: AsyncClient) -> None:
        """Ajout de mensurations retourne 201 avec valeurs correctes."""
        resp = await client.post("/api/v1/profiles/me/measurements", json={
            "measured_at": "2026-05-01", "waist_cm": 88.0, "hips_cm": 99.5,
        })
        assert resp.status_code == 201
        assert resp.json()["waist_cm"] == pytest.approx(88.0, abs=0.01)

    @pytest.mark.unit
    async def test_delete_measurements_nominal(self, client: AsyncClient) -> None:
        """Suppression de mensurations par slug retourne 204."""
        created = await client.post("/api/v1/profiles/me/measurements", json={"measured_at": "2026-05-10"})
        slug = created.json()["slug"]
        assert (await client.delete(f"/api/v1/profiles/me/measurements/{slug}")).status_code == 204