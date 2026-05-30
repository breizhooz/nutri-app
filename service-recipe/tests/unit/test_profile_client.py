import uuid
from unittest.mock import AsyncMock

import httpx

from app.schemas.nutrition_summary import NutritionSummary
from app.services.profile_client import ProfileClient


def _summary_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "profile": {"biological_sex": "male", "weight_kg": 88.5, "height_cm": 181.0},
        "calculation": {
            "bmi": 27.0,
            "bmi_category": "overweight",
            "bmr_kcal": 1900,
            "tdee_kcal": 2600,
            "pal": 1.375,
            "ideal_weight_min_kg": 60.0,
            "ideal_weight_max_kg": 80.0,
            "macros": {
                "goal": "muscle_gain",
                "tdee_kcal": 2600,
                "proteins_g": 200,
                "carbs_g": 250,
                "fats_g": 70,
                # champ inconnu côté recipe : doit être ignoré
                "proteins_kcal": 800,
            },
        },
        "nutrition_preferences": {
            "diet_type": "omnivore",
            "main_goal": "muscle_gain",
            "excluded_foods": ["arachide"],
        },
        "allergies": [{"allergen": "gluten", "severity": "intolerance"}],
        "excluded_foods": [{"food_name": "arachide", "reason": "allergie"}],
        "medical_conditions": [],
        "metabolic_medications": [
            {"medication_name": "levothyrox", "impacts_metabolism": True}
        ],
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
        uid = uuid.uuid4()
        http = _client_returning(_summary_payload(str(uid)))
        client = ProfileClient(service_token="tok", http_client=http)
        out = await client.get_nutrition_summary(uid)
        assert isinstance(out, NutritionSummary)
        assert out.user_id == uid
        assert out.calculation.tdee_kcal == 2600
        assert out.calculation.macros.proteins_g == 200
        assert out.nutrition_preferences.diet_type == "omnivore"
        assert out.allergies[0].allergen == "gluten"
        assert out.metabolic_medications[0].medication_name == "levothyrox"

    async def test_sends_service_token_header_and_url(self):
        uid = uuid.uuid4()
        http = _client_returning(_summary_payload(str(uid)))
        client = ProfileClient(
            base_url="http://profile:8000/", service_token="secret", http_client=http
        )
        await client.get_nutrition_summary(uid)
        args, kwargs = http.request.call_args
        assert args[0] == "GET"
        assert args[1] == f"http://profile:8000/api/v1/profiles/{uid}/nutrition-summary"
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
