"""Tests de la route /api/v1/nutrition-targets (cibles précalculées)."""

import pytest
from httpx import AsyncClient


def _payload(**over) -> dict:
    base = {
        "diet_type": "standard",
        "targets": {"calories": 2000, "proteines": 160, "lipides": 55, "glucides": 215},
        "excluded_foods": ["arachide"],
        "adjustment": {},
    }
    base.update(over)
    return base


class TestNutritionTargetsRoute:
    @pytest.mark.unit
    async def test_nominal_orchestration(self, service_client: AsyncClient) -> None:
        """Cibles reçues → critères de recherche."""
        resp = await service_client.post("/api/v1/nutrition-targets", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["targets"]["calories"] == 2000.0
        assert body["targets"]["proteines"] == 160.0
        criteria = body["search_criteria"]
        assert len(criteria["macro_targets"]) == 4
        assert "arachide" in criteria["excluded_terms"]

    @pytest.mark.unit
    async def test_manual_override_applied(self, service_client: AsyncClient) -> None:
        resp = await service_client.post(
            "/api/v1/nutrition-targets",
            json=_payload(adjustment={"manual_calories_override": 1800}),
        )
        assert resp.json()["targets"]["calories"] == 1800.0

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "body_field",
        ["tdee_kcal", "bmr_kcal", "weight_kg", "medical_contraindications"],
    )
    async def test_body_data_rejected(
        self, service_client: AsyncClient, body_field: str
    ) -> None:
        """Aucune donnée corporelle ou médicale n'entre dans le moteur."""
        resp = await service_client.post(
            "/api/v1/nutrition-targets", json=_payload(**{body_field: 80})
        )
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_targets_required(self, service_client: AsyncClient) -> None:
        payload = _payload()
        del payload["targets"]
        resp = await service_client.post("/api/v1/nutrition-targets", json=payload)
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_non_positive_calories_rejected(
        self, service_client: AsyncClient
    ) -> None:
        resp = await service_client.post(
            "/api/v1/nutrition-targets", json=_payload(targets={"calories": 0})
        )
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_requires_service_token(self, service_client: AsyncClient) -> None:
        resp = await service_client.post(
            "/api/v1/nutrition-targets",
            json=_payload(),
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 403
