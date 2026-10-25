import uuid
from unittest.mock import AsyncMock

import httpx

from app.schemas.nutrition_summary import NutritionSummary
from app.services.profile_client import ProfileClient


def _summary_payload(account_id: str) -> dict:
    return {
        "account_id": account_id,
        "main_goal": "muscle_gain",
        "diet_type": "omnivore",
        "excluded_foods": ["arachide"],
        "targets": {"calories": 2600, "proteines": 200, "glucides": 250, "lipides": 70},
        "rules": {"enabled": True, "variety_pct": 0.1},
        # champ inconnu côté recipe : doit être ignoré
        "schema_version": 2,
    }


def _client_returning(payload: dict, status_code: int = 200) -> AsyncMock:
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = lambda: payload
    resp.raise_for_status = lambda: None
    client = AsyncMock()
    client.request.return_value = resp
    return client


class TestProfileClient:
    async def test_disabled_without_token_returns_none(self):
        client = ProfileClient(service_token="", http_client=_client_returning({}))
        assert await client.get_nutrition_summary(uuid.uuid4()) is None

    async def test_parses_full_summary(self):
        acc = uuid.uuid4()
        http = _client_returning(_summary_payload(str(acc)))
        client = ProfileClient(service_token="tok", http_client=http)
        out = await client.get_nutrition_summary(acc)
        assert isinstance(out, NutritionSummary)
        assert out.account_id == acc
        assert out.targets.calories == 2600
        assert out.targets.proteines == 200
        assert out.diet_type == "omnivore"
        assert out.excluded_foods == ["arachide"]
        assert out.rules.enabled is True

    async def test_sends_service_token_header_and_url(self):
        uid = uuid.uuid4()
        http = _client_returning(_summary_payload(str(uid)))
        client = ProfileClient(
            base_url="http://profile:8000/", service_token="secret", http_client=http
        )
        await client.get_nutrition_summary(uid)
        args, kwargs = http.request.call_args
        assert args[0] == "GET"
        assert (
            args[1]
            == f"http://profile:8000/api/v1/internal/accounts/{uid}/nutrition-summary"
        )
        assert kwargs["headers"]["Authorization"] == "Bearer secret"

    async def test_404_returns_none(self):
        http = _client_returning({}, status_code=404)
        client = ProfileClient(service_token="tok", http_client=http)
        assert await client.get_nutrition_summary(uuid.uuid4()) is None

    async def test_network_error_returns_none(self):
        http = AsyncMock()
        http.request.side_effect = httpx.RequestError("boom")
        client = ProfileClient(service_token="tok", http_client=http)
        assert await client.get_nutrition_summary(uuid.uuid4()) is None
