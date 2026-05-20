import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.groq_extractor import GroqExtractor


def _make_groq_response(ingredients: list[dict]) -> MagicMock:
    body = json.dumps(ingredients)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": body}}]
    }
    return mock_resp


class TestGroqExtractor:
    @pytest.fixture
    def mock_http(self) -> AsyncMock:
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def extractor(self, mock_http) -> GroqExtractor:
        return GroqExtractor(http_client=mock_http)

    @pytest.mark.unit
    def test_system_prompt_is_class_attribute(self):
        """_SYSTEM_PROMPT est un attribut de classe non vide."""
        assert isinstance(GroqExtractor._SYSTEM_PROMPT, str)
        assert len(GroqExtractor._SYSTEM_PROMPT) > 0

    @pytest.mark.unit
    async def test_extract_valid_response_returns_list(self, extractor, mock_http):
        """Réponse JSON valide → liste d'ingrédients."""
        mock_http.post = AsyncMock(return_value=_make_groq_response([
            {"quantite": 200, "unite": "g", "nom": "farine de sarrasin"},
            {"quantite": 2, "unite": "cs", "nom": "huile d'olive"},
        ]))
        result = await extractor.extract("200g de farine, 2 cs d'huile")
        assert len(result) == 2
        assert result[0].nom == "farine de sarrasin"
        assert result[0].quantite == pytest.approx(200.0)
        assert result[1].unite == "cs"

    @pytest.mark.unit
    async def test_extract_malformed_json_raises_value_error(self, extractor, mock_http):
        """JSON malformé → ValueError."""
        bad = MagicMock()
        bad.raise_for_status = MagicMock()
        bad.json.return_value = {"choices": [{"message": {"content": "pas du json"}}]}
        mock_http.post = AsyncMock(return_value=bad)
        with pytest.raises(ValueError):
            await extractor.extract("some text")

    @pytest.mark.unit
    async def test_extract_skips_incomplete_items(self, extractor, mock_http):
        """Items incomplets ignorés, items valides retournés."""
        mock_http.post = AsyncMock(return_value=_make_groq_response([
            {"quantite": 100, "unite": "g", "nom": "sucre"},
            {"unite": "g"},
        ]))
        result = await extractor.extract("100g de sucre")
        assert len(result) == 1
        assert result[0].nom == "sucre"

    @pytest.mark.unit
    async def test_extract_confidence_is_0_85(self, extractor, mock_http):
        """La confiance Groq est fixée à 0.85."""
        mock_http.post = AsyncMock(return_value=_make_groq_response([
            {"quantite": 50, "unite": "g", "nom": "beurre"},
        ]))
        result = await extractor.extract("50g beurre")
        assert result[0].confidence == pytest.approx(0.85)

    @pytest.mark.unit
    async def test_extract_empty_array_returns_empty_list(self, extractor, mock_http):
        """Groq retourne [] → liste vide."""
        mock_http.post = AsyncMock(return_value=_make_groq_response([]))
        result = await extractor.extract("texte ambigu")
        assert result == []

    @pytest.mark.unit
    async def test_extract_http_error_propagates(self, extractor, mock_http):
        """Erreur HTTP → propagée."""
        bad = MagicMock()
        bad.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_http.post = AsyncMock(return_value=bad)
        with pytest.raises(httpx.HTTPStatusError):
            await extractor.extract("test")

    @pytest.mark.unit
    async def test_extract_uses_class_system_prompt(self, extractor, mock_http):
        """Le _SYSTEM_PROMPT de la classe est utilisé dans l'appel."""
        mock_http.post = AsyncMock(return_value=_make_groq_response([]))
        await extractor.extract("test")
        call_json = mock_http.post.call_args[1]["json"]
        system_msg = call_json["messages"][0]
        assert system_msg["role"] == "system"
        assert system_msg["content"] == GroqExtractor._SYSTEM_PROMPT