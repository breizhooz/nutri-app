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
        "search_criteria": {
            "excluded_terms": ["arachide"],
            "macro_targets": [{"field": "calories", "target": 1800.0, "scale": 180.0}],
        },
    }
    return resp


@pytest.fixture(autouse=True)
def _enable_nutrition_url(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_NUTRITION_URL", "http://service-nutrition")


class TestComputeTargets:
    async def test_parses_targets_and_criteria(self):
        client = AsyncMock()
        client.post = AsyncMock(return_value=_ok_response())
        svc = NutritionServiceClient(http_client=client)

        out = await svc.compute_targets(
            diet_type="standard",
            targets={"calories": 1800},
            excluded_foods=["arachide"],
        )

        assert isinstance(out, NutritionTargetsResult)
        assert out.targets["calories"] == 1800.0
        assert out.targets["warnings"] == ["plancher appliqué"]
        assert out.search_criteria.excluded_terms == ["arachide"]
        assert out.search_criteria.macro_targets[0].scale == 180.0
        assert out.search_criteria.excluded_tags == []

        args, kwargs = client.post.call_args
        assert args[0] == "/api/v1/nutrition-targets"
        assert kwargs["json"]["targets"] == {"calories": 1800}
        assert not {"tdee_kcal", "bmr_kcal", "weight_kg", "goal"} & set(kwargs["json"])
        assert kwargs["json"]["excluded_foods"] == ["arachide"]

    async def test_returns_none_when_url_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_NUTRITION_URL", "")
        svc = NutritionServiceClient(http_client=AsyncMock())
        out = await svc.compute_targets(
            diet_type="standard",
            targets={"calories": 1800},
            excluded_foods=[],
        )
        assert out is None

    async def test_returns_none_on_network_error(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.RequestError("boom"))
        svc = NutritionServiceClient(http_client=client)
        out = await svc.compute_targets(
            diet_type="standard",
            targets={"calories": 1800},
            excluded_foods=[],
        )
        assert out is None

    async def test_returns_none_on_malformed_payload(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "unexpected": True
        }  # pas de "targets"/"search_criteria"
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        svc = NutritionServiceClient(http_client=client)
        out = await svc.compute_targets(
            diet_type="standard",
            targets={"calories": 1800},
            excluded_foods=[],
        )
        assert out is None

    async def test_returns_none_on_invalid_criteria(self):
        resp = _ok_response()
        resp.json.return_value["search_criteria"] = {"macro_targets": [{"field": 1}]}
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        svc = NutritionServiceClient(http_client=client)
        out = await svc.compute_targets(
            diet_type="standard",
            targets={"calories": 1800},
            excluded_foods=[],
        )
        assert out is None
