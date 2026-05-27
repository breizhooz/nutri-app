import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

import app.services.groq_recipe_extractor as _groq_mod
from app.services.groq_recipe_extractor import GroqRecipeExtractor


def _groq_response(content: dict | str, tokens: int = 100) -> MagicMock:
    body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content)
                    if isinstance(content, dict)
                    else content
                }
            }
        ],
        "usage": {"prompt_tokens": tokens // 2, "completion_tokens": tokens // 2},
    }
    mock = MagicMock()
    mock.json.return_value = body
    mock.raise_for_status = MagicMock()
    return mock


_VALID_PAYLOAD = {
    "title": "Tarte aux pommes",
    "description": "Une tarte classique",
    "instructions": "Préchauffer le four à 180°C. Mélanger les ingrédients.",
    "servings": 6,
    "prep_time_minutes": 20,
    "cook_time_minutes": 40,
    "ingredients": [
        {"name": "farine", "quantity": 250.0, "unit": "g"},
        {"name": "beurre", "quantity": 125.0, "unit": "g"},
        {"name": "pommes", "quantity": 4.0, "unit": "pièce"},
    ],
}


class TestGroqRecipeExtractor:
    @pytest.fixture(autouse=True)
    def _patch_groq_infra(self, monkeypatch):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        monkeypatch.setattr(_groq_mod, "_get_redis", lambda: mock_redis)
        monkeypatch.setattr(_groq_mod, "_pool", None)

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        return client

    @pytest.fixture
    def extractor(self, mock_client):
        return GroqRecipeExtractor(http_client=mock_client)

    async def test_returns_extracted_recipe(self, extractor, mock_client):
        mock_client.post.return_value = _groq_response(_VALID_PAYLOAD, tokens=120)
        result = await extractor.extract("Post de recette")
        assert result.title == "Tarte aux pommes"
        assert result.description == "Une tarte classique"
        assert result.servings == 6
        assert result.prep_time_minutes == 20
        assert result.cook_time_minutes == 40

    async def test_returns_ingredients(self, extractor, mock_client):
        mock_client.post.return_value = _groq_response(_VALID_PAYLOAD, tokens=100)
        result = await extractor.extract("Post de recette")
        assert len(result.ingredients) == 3
        assert result.ingredients[0] == {
            "name": "farine",
            "quantity": 250.0,
            "unit": "g",
        }

    async def test_tokens_used_summed(self, extractor, mock_client):
        mock_client.post.return_value = _groq_response(_VALID_PAYLOAD, tokens=200)
        result = await extractor.extract("Post de recette")
        assert result.tokens_used == 200

    async def test_invalid_json_raises_value_error(self, extractor, mock_client):
        mock_client.post.return_value = _groq_response(
            "pas du json valide {{{", tokens=50
        )
        with pytest.raises(ValueError, match="JSON invalide"):
            await extractor.extract("Post de recette")

    async def test_missing_title_falls_back(self, extractor, mock_client):
        payload = {**_VALID_PAYLOAD, "title": ""}
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post")
        assert result.title == "Recette importée"

    async def test_missing_usage_defaults_to_zero(self, extractor, mock_client):
        body = {
            "choices": [{"message": {"content": json.dumps(_VALID_PAYLOAD)}}],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = body
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        result = await extractor.extract("Post")
        assert result.tokens_used == 0

    async def test_malformed_ingredient_skipped(self, extractor, mock_client):
        payload = {
            **_VALID_PAYLOAD,
            "ingredients": [
                {"name": "farine", "quantity": 200.0, "unit": "g"},
                {"quantity": 100.0},  # missing name
            ],
        }
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post")
        assert len(result.ingredients) == 1

    async def test_http_error_propagates(self, extractor, mock_client):
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=MagicMock(status_code=429)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await extractor.extract("Post")

    async def test_unit_lowercased(self, extractor, mock_client):
        payload = {
            **_VALID_PAYLOAD,
            "ingredients": [{"name": "Sucre", "quantity": 100.0, "unit": "G"}],
        }
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post")
        assert result.ingredients[0]["unit"] == "g"

    async def test_null_optional_fields(self, extractor, mock_client):
        payload = {
            **_VALID_PAYLOAD,
            "description": None,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
        }
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post")
        assert result.description is None
        assert result.prep_time_minutes is None
        assert result.cook_time_minutes is None

    async def test_is_recipe_true_by_default_when_field_absent(
        self, extractor, mock_client
    ):
        mock_client.post.return_value = _groq_response(_VALID_PAYLOAD)
        result = await extractor.extract("Post de recette")
        assert result.is_recipe is True
        assert result.recipe_confidence == 1.0

    async def test_non_recipe_returns_flag_and_low_confidence(
        self, extractor, mock_client
    ):
        payload = {
            "is_recipe": False,
            "recipe_confidence": 0.95,
            "title": "",
            "description": None,
            "instructions": "",
            "servings": 4,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
            "ingredients": [],
        }
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post hors-sujet")
        assert result.is_recipe is False
        assert result.recipe_confidence == 0.95

    async def test_confidence_clamped_to_zero_one(self, extractor, mock_client):
        payload = {**_VALID_PAYLOAD, "is_recipe": True, "recipe_confidence": 1.5}
        mock_client.post.return_value = _groq_response(payload)
        result = await extractor.extract("Post")
        assert result.recipe_confidence == 1.0

    async def test_cache_hit_defaults_confidence_fields(self, monkeypatch, mock_client):
        import json as _json

        import app.services.groq_recipe_extractor as _groq_mod
        from app.services.groq_recipe_extractor import GroqRecipeExtractor

        old_cache = {
            "title": "Vieille recette",
            "instructions": "Cuire",
            "ingredients": [],
            "tokens_used": 50,
            "description": None,
            "servings": 2,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
        }
        async def _fake_get(self, key):
            return _json.dumps(old_cache)

        mock_redis_async = type("R2", (), {"get": _fake_get})()
        monkeypatch.setattr(_groq_mod, "_get_redis", lambda: mock_redis_async)
        extractor = GroqRecipeExtractor(http_client=mock_client)
        result = await extractor.extract("Vieux post")
        assert result.is_recipe is True
        assert result.recipe_confidence == 1.0
