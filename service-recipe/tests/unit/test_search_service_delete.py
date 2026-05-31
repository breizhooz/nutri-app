from unittest.mock import AsyncMock, patch

import pytest

from app.services.search_service import search_service


@pytest.fixture
def mock_es():
    with patch("app.core.elasticsearch.es_client") as es:
        es.delete_by_query = AsyncMock(return_value={"deleted": 0})
        yield es


@pytest.mark.asyncio
async def test_delete_by_user_filters_on_author(mock_es):
    await search_service.delete_by_user("user-42")
    mock_es.delete_by_query.assert_awaited_once()
    kwargs = mock_es.delete_by_query.call_args.kwargs
    assert kwargs["query"] == {"term": {"created_by_user_id.keyword": "user-42"}}
    assert kwargs["index"] == search_service.index_name
    assert kwargs["conflicts"] == "proceed"
