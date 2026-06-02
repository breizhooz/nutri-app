from unittest.mock import AsyncMock

import httpx

from app.services.unsplash_service import ImageSuggestion, UnsplashService


def _photo(pid: str) -> dict:
    return {
        "id": pid,
        "urls": {"thumb": f"http://thumb/{pid}", "regular": f"http://hd/{pid}"},
        "links": {"download_location": f"http://dl/{pid}"},
        "user": {"name": "Jane Doe", "links": {"html": "http://author/jane"}},
    }


def _client_returning(payload: dict, status_code: int = 200) -> AsyncMock:
    resp = AsyncMock(spec=httpx.Response)
    resp.json = lambda: payload
    resp.raise_for_status = lambda: None
    client = AsyncMock()
    client.request.return_value = resp
    return client


class TestUnsplashSearch:
    async def test_returns_empty_when_no_access_key(self):
        service = UnsplashService(access_key="")
        assert await service.search("tarte") == []

    async def test_returns_empty_on_blank_keyword(self):
        service = UnsplashService(access_key="key", http_client=_client_returning({}))
        assert await service.search("   ") == []

    async def test_maps_results_to_suggestions(self):
        client = _client_returning({"results": [_photo("a"), _photo("b")]})
        service = UnsplashService(access_key="key", http_client=client)
        out = await service.search("tarte", count=4)
        assert len(out) == 2
        assert isinstance(out[0], ImageSuggestion)
        assert out[0].unsplash_id == "a"
        assert out[0].thumb_url == "http://thumb/a"
        assert out[0].full_url == "http://hd/a"
        assert out[0].download_location == "http://dl/a"
        assert out[0].author == "Jane Doe"

    async def test_respects_count_limit(self):
        client = _client_returning({"results": [_photo(str(i)) for i in range(10)]})
        service = UnsplashService(access_key="key", http_client=client)
        out = await service.search("tarte", count=4)
        assert len(out) == 4

    async def test_sends_client_id_header(self):
        client = _client_returning({"results": []})
        service = UnsplashService(access_key="secret-key", http_client=client)
        await service.search("tarte")
        _, kwargs = client.request.call_args
        assert kwargs["headers"]["Authorization"] == "Client-ID secret-key"

    async def test_network_error_returns_empty(self):
        client = AsyncMock()
        client.request.side_effect = httpx.RequestError("boom")
        service = UnsplashService(access_key="key", http_client=client)
        assert await service.search("tarte") == []

    async def test_rate_limit_raises_unavailable(self):
        import pytest
        from app.core.exceptions import ImageServiceUnavailable

        req = httpx.Request("GET", "http://x")
        for code in (403, 429):
            client = AsyncMock()
            client.request.side_effect = httpx.HTTPStatusError(
                "limit", request=req, response=httpx.Response(code, request=req)
            )
            service = UnsplashService(access_key="key", http_client=client)
            with pytest.raises(ImageServiceUnavailable):
                await service.search("saumon")

    async def test_other_http_status_returns_empty(self):
        req = httpx.Request("GET", "http://x")
        client = AsyncMock()
        client.request.side_effect = httpx.HTTPStatusError(
            "boom", request=req, response=httpx.Response(500, request=req)
        )
        service = UnsplashService(access_key="key", http_client=client)
        assert await service.search("saumon") == []


class TestUnsplashTrackDownload:
    async def test_noop_when_disabled(self):
        client = _client_returning({})
        service = UnsplashService(access_key="", http_client=client)
        await service.track_download("http://dl/a")
        client.request.assert_not_called()

    async def test_noop_when_no_location(self):
        client = _client_returning({})
        service = UnsplashService(access_key="key", http_client=client)
        await service.track_download("")
        client.request.assert_not_called()

    async def test_calls_download_location(self):
        client = _client_returning({})
        service = UnsplashService(access_key="key", http_client=client)
        await service.track_download("http://dl/a")
        client.request.assert_called_once()

    async def test_swallows_errors(self):
        client = AsyncMock()
        client.request.side_effect = httpx.RequestError("boom")
        service = UnsplashService(access_key="key", http_client=client)
        await service.track_download("http://dl/a")  # must not raise
