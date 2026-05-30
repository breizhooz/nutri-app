from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import settings
from app.core.http_client import NutritionServiceClient, NutritionTargetsResult


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "targets": {
            "calories": 1800.0,
            "proteines": 160.0,
            "lipides": 55.6,
            "glucides": 215.0,
            "warnings": ["plancher appliqué"],
        },
        "search_query": {"query": {"function_score": {"functions": []}}},
    }
    return resp


@pytest.fixture(autouse=True)
def _enable_nutrition_url(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_NUTRITION_URL", "http://service-nutrition")


class TestComputeTargets:
    async def test_parses_targets_and_query(self):
        client = AsyncMock()
        client.post = AsyncMock(return_value=_ok_response())
        svc = NutritionServiceClient(http_client=client)

        out = await svc.compute_targets(
            goal="weight_loss",
            diet_type="standard",
            tdee_kcal=2500,
            bmr_kcal=1700,
            weight_kg=80,
            excluded_foods=["arachide"],
            medical_contraindications=["gluten"],
        )

        assert isinstance(out, NutritionTargetsResult)
        assert out.targets["calories"] == 1800.0
        assert out.targets["warnings"] == ["plancher appliqué"]
        assert "function_score" in out.search_query["query"]

        args, kwargs = client.post.call_args
        assert args[0] == "/api/v1/nutrition-targets"
        assert kwargs["json"]["goal"] == "weight_loss"
        assert kwargs["json"]["excluded_foods"] == ["arachide"]

    async def test_returns_none_when_url_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_NUTRITION_URL", "")
        svc = NutritionServiceClient(http_client=AsyncMock())
        out = await svc.compute_targets(
            goal="maintenance",
            diet_type="standard",
            tdee_kcal=2000,
            bmr_kcal=1500,
            weight_kg=70,
            excluded_foods=[],
            medical_contraindications=[],
        )
        assert out is None

    async def test_returns_none_on_network_error(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.RequestError("boom"))
        svc = NutritionServiceClient(http_client=client)
        out = await svc.compute_targets(
            goal="maintenance",
            diet_type="standard",
            tdee_kcal=2000,
            bmr_kcal=1500,
            weight_kg=70,
            excluded_foods=[],
            medical_contraindications=[],
        )
        assert out is None

    async def test_returns_none_on_malformed_payload(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"unexpected": True}  # pas de "targets"/"search_query"
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        svc = NutritionServiceClient(http_client=client)
        out = await svc.compute_targets(
            goal="maintenance",
            diet_type="standard",
            tdee_kcal=2000,
            bmr_kcal=1500,
            weight_kg=70,
            excluded_foods=[],
            medical_contraindications=[],
        )
        assert out is None
