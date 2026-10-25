"""Route GET /search/recipes : validation et transmission au service.

Le SQL de la recherche (plein texte, filtres, scoring) est testé sur un vrai
PostgreSQL dans ``test_search_postgres.py``.
"""

from unittest.mock import AsyncMock

import pytest

from app.api.routes.search import get_nutrition_rules_service
from app.main import app

from .conftest import TEST_ACCOUNT_ID

SEARCH_BASE = "/api/v1/search/recipes"


@pytest.fixture
def rules_service():
    service = AsyncMock()
    service.search.return_value = {
        "total": 1,
        "limit": 10,
        "offset": 0,
        "results": [{"id": 1, "score": 1.0, "title": "Tarte aux pommes"}],
    }
    app.dependency_overrides[get_nutrition_rules_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_nutrition_rules_service, None)


def _kwargs(service) -> dict:
    return service.search.call_args.kwargs


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_returns_service_response(rules_service, http_client):
    async with http_client as client:
        response = await client.get(SEARCH_BASE, params={"q": "tarte"})
    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "Tarte aux pommes"
    assert _kwargs(rules_service)["query"] == "tarte"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_scoped_to_active_account(rules_service, http_client):
    """Multicomptes : recettes et règles bornées au compte actif."""
    async with http_client as client:
        await client.get(SEARCH_BASE)
    kwargs = _kwargs(rules_service)
    assert kwargs["account_id"] == TEST_ACCOUNT_ID
    assert "user_id" not in kwargs


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_forwards_filters(rules_service, http_client):
    async with http_client as client:
        await client.get(
            SEARCH_BASE,
            params=[
                ("difficulty", "enums.difficulty.easy"),
                ("max_prep_time", "30"),
                ("exclude_allergens", "enums.allergen.gluten"),
                ("exclude_allergens", "enums.allergen.milk"),
                ("limit", "5"),
                ("offset", "20"),
                ("apply_rules", "false"),
            ],
        )
    kwargs = _kwargs(rules_service)
    assert kwargs["difficulty"] == "enums.difficulty.easy"
    assert kwargs["max_prep_time"] == 30
    assert kwargs["exclude_allergens"] == [
        "enums.allergen.gluten",
        "enums.allergen.milk",
    ]
    assert (kwargs["limit"], kwargs["offset"]) == (5, 20)
    assert kwargs["apply_rules"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_limit_max_returns_422(rules_service, http_client):
    async with http_client as client:
        response = await client.get(SEARCH_BASE, params={"limit": 200})
    assert response.status_code == 422
    rules_service.search.assert_not_called()
