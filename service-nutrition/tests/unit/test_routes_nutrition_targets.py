"""Tests de la route d'orchestration /api/v1/nutrition-targets."""

import pytest
from httpx import AsyncClient


def _payload(**over) -> dict:
    base = {
        "goal": "weight_loss",
        "diet_type": "standard",
        "tdee_kcal": 2500,
        "bmr_kcal": 1700,
        "weight_kg": 80,
        "excluded_foods": ["arachide"],
        "medical_contraindications": [],
        "adjustment": {},
    }
    base.update(over)
    return base


class TestNutritionTargetsRoute:
    @pytest.mark.unit
    async def test_nominal_orchestration(self, service_client: AsyncClient) -> None:
        """Enchaîne les 3 étapes et retourne cibles + requête ES."""
        resp = await service_client.post("/api/v1/nutrition-targets", json=_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["targets"]["calories"] == 2000.0
        assert body["targets"]["proteines"] == 160.0
        assert "function_score" in body["search_query"]["query"]
        # exclusion propagée jusqu'à la requête
        assert "arachide" in str(body["search_query"])

    @pytest.mark.unit
    async def test_warnings_propagated_to_response(
        self, service_client: AsyncClient
    ) -> None:
        """Un override sous le plancher remonte un warning dans la réponse API."""
        resp = await service_client.post(
            "/api/v1/nutrition-targets",
            json=_payload(adjustment={"manual_calories_override": 1000}),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["targets"]["calories"] == 1800.0
        assert len(body["targets"]["warnings"]) >= 1

    @pytest.mark.unit
    async def test_unknown_goal_returns_422(self, service_client: AsyncClient) -> None:
        resp = await service_client.post(
            "/api/v1/nutrition-targets", json=_payload(goal="cheat_day")
        )
        assert resp.status_code == 422
