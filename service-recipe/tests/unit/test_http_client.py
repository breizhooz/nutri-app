import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.http_client import ServicesUserClient

def _make_response(exists: bool)-> MagicMock:
    response = MagicMock()
    response.json.return_value = {"exists": exists}
    response.raise_for_status.return_value = None
    return response

@pytest.fixture
def mock_httpx_client():
    """
    Mock of httpx.Asyncclient inside ServicesUserClient
    """
    mock_instance = AsyncMock()
    mock_instance.aclose = AsyncMock()
    with patch("app.core.http_client.httpx.AsyncClient", return_value=mock_instance):
        yield mock_instance

@pytest.mark.asyncio
async def test_user_exist_returns_true_when_api_says_exists(mock_httpx_client):
    mock_httpx_client.get = AsyncMock(return_value=_make_response(exists=True))

    async with ServicesUserClient() as client:
        result = await client.user_exist("123e4567-e89b-12d3-a456-426614174000")

    assert result is True
    mock_httpx_client.get.assert_called_once_with(
        "/api/v1/users/123e4567-e89b-12d3-a456-426614174000/exists"
    )

@pytest.mark.asyncio
async def test_user_exist_returns_false_when_api_says_not_exists(mock_httpx_client):
    mock_httpx_client.get = AsyncMock(return_value=_make_response(exists=False))

    async with ServicesUserClient() as client:
        result = await client.user_exist("dead-beef-0000-0000-0000-000000000000")

    assert result is False

@pytest.mark.asyncio
async def test_user_exist_raises_on_network_error(mock_httpx_client):
    import httpx
    from app.core.http_client import ServiceUnavailableError

    mock_httpx_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

    with pytest.raises(ServiceUnavailableError):
        async with ServicesUserClient() as client:
            await client.user_exist("any-id")

@pytest.mark.asyncio
async def test_user_exist_returns_false_on_404(mock_httpx_client):
    import httpx
    response = _make_response(exists=False)
    mock_http_response = MagicMock()
    mock_http_response.status_code = 404             # ← explicite
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=mock_http_response
    )
    mock_httpx_client.get = AsyncMock(return_value=response)

    async with ServicesUserClient() as client:
        result = await client.user_exist("000-not-found")

    assert result is False

@pytest.mark.asyncio
async def test_client_closes_on_exit(mock_httpx_client):
    mock_httpx_client.get = AsyncMock(return_value=_make_response(exists=True))

    async with ServicesUserClient() as client:
        await client.user_exist("any-id")

    mock_httpx_client.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_user_exist_raises_on_5xx(mock_httpx_client):
    import httpx
    from app.core.http_client import ServiceUnavailableError

    response = _make_response(exists=False)
    mock_http_response = MagicMock()
    mock_http_response.status_code = 503
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=mock_http_response
    )
    mock_httpx_client.get = AsyncMock(return_value=response)

    with pytest.raises(ServiceUnavailableError):
        async with ServicesUserClient() as client:
            await client.user_exist("any-id")
