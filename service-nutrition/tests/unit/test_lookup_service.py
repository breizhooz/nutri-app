from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.lookup_service import LookupService


def _make_es_response(hits: list[dict]):
    return {"hits": {"hits": hits}}


def _hit(slug: str, score: float) -> dict:
    return {
        "_score": score,
        "_source": {
            "slug": slug,
            "nom_fr": "Farine de sarrasin",
            "calories": 340.0,
            "proteines": 13.0,
            "glucides": 71.0,
            "lipides": 3.0,
            "fibres": 3.5,
        },
    }


class TestLookupService:
    @pytest.fixture
    def mock_es(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def svc(self, mock_es) -> LookupService:
        return LookupService(es_client=mock_es)

    @pytest.mark.unit
    async def test_search_above_threshold_returns_result(self, svc, mock_es):
        """Score ≥ seuil → résultat retourné."""
        mock_es.search = AsyncMock(return_value=_make_es_response([_hit("farine", 5.0)]))
        results = await svc.search("farine")
        assert len(results) == 1
        assert results[0].slug == "farine"
        assert results[0].score == pytest.approx(5.0)

    @pytest.mark.unit
    async def test_search_below_threshold_excluded(self, svc, mock_es):
        """Score < seuil → résultat exclu."""
        mock_es.search = AsyncMock(return_value=_make_es_response([_hit("farine", 0.5)]))
        assert await svc.search("farine") == []

    @pytest.mark.unit
    async def test_search_no_hits_returns_empty(self, svc, mock_es):
        mock_es.search = AsyncMock(return_value=_make_es_response([]))
        assert await svc.search("gochujank") == []

    @pytest.mark.unit
    async def test_search_es_exception_returns_empty(self, svc, mock_es):
        """Exception ES → liste vide, pas de propagation."""
        mock_es.search = AsyncMock(side_effect=Exception("ES down"))
        assert await svc.search("farine") == []

    @pytest.mark.unit
    async def test_search_multiple_results_in_order(self, svc, mock_es):
        """Plusieurs hits → retournés dans l'ordre ES (score décroissant)."""
        mock_es.search = AsyncMock(return_value=_make_es_response([
            _hit("farine-ble", 8.0),
            _hit("farine-sarrasin", 5.0),
        ]))
        results = await svc.search("farine")
        assert len(results) == 2
        assert results[0].slug == "farine-ble"
        assert results[1].slug == "farine-sarrasin"

    @pytest.mark.unit
    async def test_search_filters_partial_below_threshold(self, svc, mock_es):
        """1 hit au-dessus, 1 en-dessous → seul le premier retourné."""
        mock_es.search = AsyncMock(return_value=_make_es_response([
            _hit("ok", 3.0),
            _hit("trop-faible", 0.2),
        ]))
        results = await svc.search("test")
        assert len(results) == 1
        assert results[0].slug == "ok"

    @pytest.mark.unit
    async def test_index_item_calls_es_index(self, svc, mock_es):
        """index_item() appelle client.index() avec le bon id."""
        item = MagicMock()
        item.id = "abc-123"
        item.slug = "farine"
        item.nom_fr = "Farine"
        item.nom_en = None
        item.calories = item.proteines = item.glucides = item.lipides = item.fibres = 0
        mock_es.index = AsyncMock()
        await svc.index_item(item)
        mock_es.index.assert_called_once()
        call_kwargs = mock_es.index.call_args[1]
        assert call_kwargs["id"] == "abc-123"

    @pytest.mark.unit
    async def test_index_item_es_error_not_propagated(self, svc, mock_es):
        """Erreur ES lors de l'indexation → loguée, pas propagée."""
        item = MagicMock()
        item.id = "x"
        item.slug = item.nom_fr = "x"
        item.nom_en = item.fibres = None
        item.calories = item.proteines = item.glucides = item.lipides = 0
        mock_es.index = AsyncMock(side_effect=Exception("ES boom"))
        await svc.index_item(item)  # ne lève pas