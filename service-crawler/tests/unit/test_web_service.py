import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.web_service import WebService

_LONG_TEXT = "x" * 300


@pytest.mark.asyncio
async def test_fetch_extracts_title_and_content():
    html = f"<html><head><title>Pasta Recipe</title></head><body><article>{_LONG_TEXT}</article></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.web_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        result = await WebService().fetch("https://example.com/recipe")

    assert result["title"] == "Pasta Recipe"
    assert _LONG_TEXT[:10] in result["raw_content"]
    assert result["video_url"] is None


@pytest.mark.asyncio
async def test_fetch_falls_back_to_h1_when_no_title_tag():
    html = f"<html><body><h1>Ma Recette</h1><article>{_LONG_TEXT}</article></body></html>"
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.web_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        result = await WebService().fetch("https://example.com")

    assert result["title"] == "Ma Recette"


@pytest.mark.asyncio
async def test_fetch_resolves_relative_image_urls():
    html = (
        f"<html><head><title>T</title></head><body><article>{_LONG_TEXT}</article>"
        '<img src="/images/photo.jpg">'
        '<img src="https://cdn.example.com/img.png">'
        "</body></html>"
    )
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.web_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        result = await WebService().fetch("https://example.com/recipe")

    assert "https://example.com/images/photo.jpg" in result["images"]
    assert "https://cdn.example.com/img.png" in result["images"]


@pytest.mark.asyncio
async def test_fetch_triggers_playwright_fallback_on_js_site():
    html_js = "<html><body><div id='root'></div></body></html>"
    mock_response = MagicMock()
    mock_response.text = html_js
    mock_response.raise_for_status = MagicMock()

    playwright_result = {"title": "JS App", "raw_content": _LONG_TEXT, "images": [], "video_url": None}

    with patch("app.services.web_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        with patch.object(WebService, "_fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
            mock_pw.return_value = playwright_result
            result = await WebService().fetch("https://js-app.com")

        mock_pw.assert_called_once_with("https://js-app.com")

    assert result["title"] == "JS App"


@pytest.mark.asyncio
async def test_fetch_triggers_playwright_fallback_on_http_error():
    with patch("app.services.web_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        with patch.object(WebService, "_fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
            mock_pw.return_value = {"title": "Fallback", "raw_content": "content", "images": [], "video_url": None}
            result = await WebService().fetch("https://example.com")

        mock_pw.assert_called_once()

    assert result["title"] == "Fallback"


def test_parse_html_limits_images_to_20():
    service = WebService()
    imgs = "".join(f'<img src="https://example.com/img{i}.jpg">' for i in range(30))
    html = f"<html><body>{imgs}</body></html>"
    result = service._parse_html("https://example.com", html)
    assert len(result["images"]) == 20


def test_parse_html_ignores_data_uris():
    service = WebService()
    html = '<html><body><img src="data:image/png;base64,abc123"><img src="https://ok.com/img.jpg"></body></html>'
    result = service._parse_html("https://example.com", html)
    assert len(result["images"]) == 1
    assert result["images"][0] == "https://ok.com/img.jpg"


def test_get_set_js_threshold():
    original = WebService.get_js_threshold()
    WebService.set_js_threshold(value=500)
    assert WebService.get_js_threshold() == 500
    WebService.set_js_threshold(value=original)