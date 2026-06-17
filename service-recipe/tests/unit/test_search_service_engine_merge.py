from unittest.mock import AsyncMock, patch

import pytest

from app.services.search_service import search_service

_ES_RESPONSE = {"hits": {"hits": [], "total": {"value": 0}}}


@pytest.fixture
def mock_es():
    with patch("app.core.elasticsearch.es_client") as es:
        es.search = AsyncMock(return_value=_ES_RESPONSE)
        yield es


def _query(mock_es) -> dict:
    return mock_es.search.call_args.kwargs["query"]


class TestSearchEngineMerge:
    async def test_extra_clauses_merged_into_bool(self, mock_es):
        await search_service.search_recipes(
            account_id="u1",
            extra_must_not=[{"terms": {"ingredient_names": ["porc"]}}],
            extra_filter=[{"exists": {"field": "course_type"}}],
        )
        bool_q = _query(mock_es)["bool"]
        # scoping user toujours présent
        assert {"term": {"account_id": "u1"}} in bool_q["filter"]
        # clauses moteur fusionnées
        assert {"terms": {"ingredient_names": ["porc"]}} in bool_q["must_not"]
        assert {"exists": {"field": "course_type"}} in bool_q["filter"]

    async def test_scoring_wraps_in_function_score(self, mock_es):
        await search_service.search_recipes(
            account_id="u1",
            scoring_functions=[{"gauss": {"calories": {"origin": 2000, "scale": 200}}}],
        )
        q = _query(mock_es)
        assert "function_score" in q
        fs = q["function_score"]
        assert fs["score_mode"] == "sum"
        assert fs["boost_mode"] == "multiply"
        assert fs["functions"] == [
            {"gauss": {"calories": {"origin": 2000, "scale": 200}}}
        ]
        # le bool reste à l'intérieur, avec le scoping user
        assert {"term": {"account_id": "u1"}} in fs["query"]["bool"]["filter"]

    async def test_no_extras_stays_plain_bool(self, mock_es):
        await search_service.search_recipes(account_id="u1")
        q = _query(mock_es)
        assert "function_score" not in q
        assert "bool" in q
