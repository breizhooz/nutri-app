"""Tests unitaires — NotificationClient."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.notification_client import NotificationClient


def _make_client(injected: AsyncMock) -> NotificationClient:
    return NotificationClient(http_client=injected)


def _mock_http_client(status_code: int = 200) -> AsyncMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = status_code
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.return_value = resp
    return client


@pytest.mark.anyio
async def test_notify_crawl_done_calls_post():
    http = _mock_http_client()
    await _make_client(http).notify_crawl_done("user-id-123", "web", 3, "https://example.com")
    http.post.assert_called_once()
    call_args = http.post.call_args
    assert call_args[0][0] == "/api/v1/notify"
    payload = call_args[1]["json"]
    assert payload["user_slug"] == "user-id-123"
    assert payload["type"] == "crawl_done"
    assert "3" in payload["body"]
    assert "example.com" in payload["body"]


@pytest.mark.anyio
async def test_notify_crawl_done_falls_back_to_source_type_in_body():
    http = _mock_http_client()
    await _make_client(http).notify_crawl_done("user-id-123", "instagram", 1)
    payload = http.post.call_args[1]["json"]
    assert "instagram" in payload["body"]


@pytest.mark.anyio
async def test_notify_crawl_done_data_fields():
    http = _mock_http_client()
    await _make_client(http).notify_crawl_done("uid", "web", 5, "label")
    payload = http.post.call_args[1]["json"]
    assert payload["data"]["source_type"] == "web"
    assert payload["data"]["new_count"] == 5


@pytest.mark.anyio
async def test_notify_crawl_done_http_error_is_swallowed():
    http = AsyncMock()
    http.__aenter__.return_value = http
    http.__aexit__.return_value = None
    http.post.side_effect = httpx.ConnectError("refused")
    await _make_client(http).notify_crawl_done("uid", "web", 1)


@pytest.mark.anyio
async def test_notify_crawl_done_raise_for_status_error_is_swallowed():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    http = AsyncMock()
    http.__aenter__.return_value = http
    http.__aexit__.return_value = None
    http.post.return_value = resp
    await _make_client(http).notify_crawl_done("uid", "web", 1)


@pytest.mark.anyio
async def test_notify_crawl_error_calls_post():
    http = _mock_http_client()
    await _make_client(http).notify_crawl_error("user-id-456", "Playwright timeout")
    http.post.assert_called_once()
    payload = http.post.call_args[1]["json"]
    assert payload["user_slug"] == "user-id-456"
    assert payload["type"] == "system"
    assert payload["body"] == "Playwright timeout"


@pytest.mark.anyio
async def test_notify_crawl_error_http_error_is_swallowed():
    http = AsyncMock()
    http.__aenter__.return_value = http
    http.__aexit__.return_value = None
    http.post.side_effect = httpx.ConnectError("refused")
    await _make_client(http).notify_crawl_error("uid", "error message")


@pytest.mark.anyio
async def test_injected_client_used_directly():
    http = _mock_http_client()
    client = NotificationClient(http_client=http)
    async with client._client() as c:
        assert c is http


@pytest.mark.anyio
async def test_production_client_uses_settings():
    with patch("app.services.notification_client.httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_cls.return_value = mock_instance

        client = NotificationClient()
        async with client._client() as c:
            assert c is mock_instance

        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert "service-notification" in call_kwargs["base_url"]