from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.recipe_service_client import RecipeServiceClient


def _make_response(json_data, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            str(status_code),
            request=MagicMock(),
            response=MagicMock(status_code=status_code),
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


class TestFindIngredientByName:
    @pytest.fixture
    def mock_http(self):
        return AsyncMock(spec=httpx.AsyncClient)

    async def test_returns_id_when_found(self, mock_http):
        mock_http.get.return_value = _make_response(
            [{"id": 3, "name": "Farine"}, {"id": 7, "name": "Beurre"}]
        )
        client = RecipeServiceClient(http_client=mock_http)
        result = await client.find_ingredient_by_name("farine")
        assert result == 3

    async def test_case_insensitive_match(self, mock_http):
        mock_http.get.return_value = _make_response([{"id": 5, "name": "SUCRE"}])
        client = RecipeServiceClient(http_client=mock_http)
        assert await client.find_ingredient_by_name("sucre") == 5

    async def test_returns_none_when_not_found(self, mock_http):
        mock_http.get.return_value = _make_response([{"id": 1, "name": "sel"}])
        client = RecipeServiceClient(http_client=mock_http)
        assert await client.find_ingredient_by_name("poivre") is None

    async def test_returns_none_on_empty_list(self, mock_http):
        mock_http.get.return_value = _make_response([])
        client = RecipeServiceClient(http_client=mock_http)
        assert await client.find_ingredient_by_name("farine") is None

    async def test_raises_on_http_error(self, mock_http):
        mock_http.get.return_value = _make_response({}, status_code=500)
        client = RecipeServiceClient(http_client=mock_http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.find_ingredient_by_name("farine")

    async def test_raises_on_connection_error(self, mock_http):
        mock_http.get.side_effect = httpx.RequestError("timeout", request=MagicMock())
        client = RecipeServiceClient(http_client=mock_http)
        with pytest.raises(httpx.RequestError):
            await client.find_ingredient_by_name("farine")


class TestCreateIngredient:
    @pytest.fixture
    def mock_http(self):
        return AsyncMock(spec=httpx.AsyncClient)

    async def test_returns_new_id(self, mock_http):
        mock_http.post.return_value = _make_response({"id": 42, "name": "tomate"})
        client = RecipeServiceClient(http_client=mock_http)
        assert await client.create_ingredient("tomate") == 42

    async def test_sends_correct_payload(self, mock_http):
        mock_http.post.return_value = _make_response({"id": 1, "name": "ail"})
        client = RecipeServiceClient(http_client=mock_http)
        await client.create_ingredient("ail")
        _, kwargs = mock_http.post.call_args
        body = kwargs["json"]
        assert body["name"] == "ail"
        assert body["tags"] == []
        assert body["free_tags"] == []

    async def test_raises_on_http_error(self, mock_http):
        mock_http.post.return_value = _make_response({}, status_code=422)
        client = RecipeServiceClient(http_client=mock_http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.create_ingredient("ail")


class TestGetOrCreateIngredient:
    @pytest.fixture
    def mock_http(self):
        return AsyncMock(spec=httpx.AsyncClient)

    async def test_returns_existing_id_without_creating(self, mock_http):
        mock_http.get.return_value = _make_response([{"id": 10, "name": "oignon"}])
        client = RecipeServiceClient(http_client=mock_http)
        result = await client.get_or_create_ingredient("oignon")
        assert result == 10
        mock_http.post.assert_not_called()

    async def test_creates_when_not_found(self, mock_http):
        mock_http.get.return_value = _make_response([])
        mock_http.post.return_value = _make_response({"id": 99, "name": "courgette"})
        client = RecipeServiceClient(http_client=mock_http)
        result = await client.get_or_create_ingredient("courgette")
        assert result == 99
        mock_http.post.assert_called_once()


class TestCreateRecipe:
    @pytest.fixture
    def mock_http(self):
        return AsyncMock(spec=httpx.AsyncClient)

    async def test_returns_recipe_dict(self, mock_http):
        payload = {"title": "Tarte", "instructions": "...", "recipe_ingredients": []}
        mock_http.post.return_value = _make_response({"id": 1, "title": "Tarte"})
        client = RecipeServiceClient(http_client=mock_http)
        result = await client.create_recipe(payload)
        assert result["id"] == 1

    async def test_posts_to_correct_path(self, mock_http):
        mock_http.post.return_value = _make_response({"id": 2})
        client = RecipeServiceClient(http_client=mock_http)
        await client.create_recipe({"title": "X", "instructions": "Y", "recipe_ingredients": []})
        args, _ = mock_http.post.call_args
        assert args[0] == "/api/v1/recipe/"

    async def test_raises_on_http_error(self, mock_http):
        mock_http.post.return_value = _make_response({}, status_code=500)
        client = RecipeServiceClient(http_client=mock_http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.create_recipe({})