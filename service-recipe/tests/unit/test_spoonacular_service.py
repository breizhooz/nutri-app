from unittest.mock import AsyncMock

import httpx

from app.services.spoonacular_service import SpoonacularClient, SpoonacularRecipe


def _recipe(rid: int) -> dict:
    return {
        "id": rid,
        "title": f"Recette {rid}",
        "image": f"http://img/{rid}.jpg",
        "sourceUrl": f"http://src/{rid}",
        "extendedIngredients": [{"name": "farine"}],
    }


def _client_returning(payload: dict) -> AsyncMock:
    resp = AsyncMock(spec=httpx.Response)
    resp.json = lambda: payload
    resp.raise_for_status = lambda: None
    client = AsyncMock()
    client.request.return_value = resp
    return client


class TestRandomRecipes:
    async def test_returns_empty_when_no_api_key(self):
        client = SpoonacularClient(api_key="")
        assert await client.random_recipes() == []

    async def test_maps_results_to_dataclass(self):
        http = _client_returning({"recipes": [_recipe(1), _recipe(2)]})
        client = SpoonacularClient(api_key="key", http_client=http)
        out = await client.random_recipes(2)
        assert len(out) == 2
        assert isinstance(out[0], SpoonacularRecipe)
        assert out[0].spoonacular_id == 1
        assert out[0].title == "Recette 1"
        assert out[0].image_url == "http://img/1.jpg"
        assert out[0].source_url == "http://src/1"
        assert out[0].payload["extendedIngredients"] == [{"name": "farine"}]

    async def test_clamps_count_to_max_5(self):
        http = _client_returning({"recipes": []})
        client = SpoonacularClient(api_key="key", http_client=http)
        await client.random_recipes(50)
        _, kwargs = http.request.call_args
        assert kwargs["params"]["number"] == 5

    async def test_clamps_count_to_min_1(self):
        http = _client_returning({"recipes": []})
        client = SpoonacularClient(api_key="key", http_client=http)
        await client.random_recipes(0)
        _, kwargs = http.request.call_args
        assert kwargs["params"]["number"] == 1

    async def test_sends_api_key_header(self):
        http = _client_returning({"recipes": []})
        client = SpoonacularClient(api_key="secret-key", http_client=http)
        await client.random_recipes()
        _, kwargs = http.request.call_args
        assert kwargs["headers"]["x-api-key"] == "secret-key"

    async def test_skips_entries_without_id(self):
        http = _client_returning({"recipes": [{"title": "no id"}, _recipe(7)]})
        client = SpoonacularClient(api_key="key", http_client=http)
        out = await client.random_recipes()
        assert [r.spoonacular_id for r in out] == [7]

    async def test_network_error_returns_empty(self):
        http = AsyncMock()
        http.request.side_effect = httpx.RequestError("boom")
        client = SpoonacularClient(api_key="key", http_client=http)
        assert await client.random_recipes() == []

    async def test_http_status_error_returns_empty(self):
        req = httpx.Request("GET", "http://x")
        http = AsyncMock()
        http.request.side_effect = httpx.HTTPStatusError(
            "quota", request=req, response=httpx.Response(402, request=req)
        )
        client = SpoonacularClient(api_key="key", http_client=http)
        assert await client.random_recipes() == []
