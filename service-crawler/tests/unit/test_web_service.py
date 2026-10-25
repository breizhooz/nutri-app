import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.web_service import (
    InsufficientContentError,
    PermanentFetchError,
    WebService,
)

_LONG_TEXT = "x" * 300


@pytest.fixture(autouse=True)
def _allow_all_urls():
    """Neutralise le garde anti-SSRF pour ces tests (qui valident le parsing /
    le fallback, pas la résolution réseau). Le garde a sa propre suite dédiée
    dans ``test_ssrf.py``."""
    with patch("app.services.web_service.assert_public_url", return_value=None):
        yield


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
    html = (
        f"<html><body><h1>Ma Recette</h1><article>{_LONG_TEXT}</article></body></html>"
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


def _patch_http(response=None, side_effect=None):
    """Remplace httpx.AsyncClient par un client dont ``get`` renvoie ``response``
    (ou lève ``side_effect``)."""
    patcher = patch("app.services.web_service.httpx.AsyncClient")
    mock_cls = patcher.start()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response, side_effect=side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_cls.return_value = mock_client
    return patcher


def _http_response(status: int, html: str = "") -> httpx.Response:
    return httpx.Response(
        status, text=html, request=httpx.Request("GET", "https://example.com")
    )


_JS_PAGE_WITH_SCHEMA = (
    "<html><head><title>Page JS</title>"
    '<script type="application/ld+json">'
    '{"@context": "https://schema.org", "@type": "Recipe", "name": "Tarte",'
    ' "recipeIngredient": ["3 pommes", "200 g de farine"],'
    ' "recipeInstructions": "Cuire 30 minutes."}'
    "</script></head><body><div id='root'></div></body></html>"
)


@pytest.mark.asyncio
async def test_fetch_uses_schema_recipe_on_js_site():
    """Site rendu en JS (texte vide) mais recette schema.org dans le HTML initial."""
    patcher = _patch_http(_http_response(200, _JS_PAGE_WITH_SCHEMA))
    try:
        result = await WebService().fetch("https://js-app.com/tarte")
    finally:
        patcher.stop()

    assert result["title"] == "Tarte"
    assert "- 3 pommes" in result["raw_content"]
    assert "Étape 1 : Cuire 30 minutes." in result["raw_content"]


@pytest.mark.asyncio
async def test_fetch_prefers_schema_over_page_text_and_merges_images():
    html = (
        f"<html><head><title>Titre page</title></head><body><article>{_LONG_TEXT}"
        '</article><img src="https://ex.com/a.jpg"><img src="https://ex.com/b.jpg">'
        "</body></html>"
    )
    extractor = MagicMock()
    extractor.extract = MagicMock(
        return_value={
            "title": "",
            "raw_content": "Ingrédients :\n- 1 pomme",
            "images": ["https://ex.com/b.jpg"],
            "video_url": None,
        }
    )
    patcher = _patch_http(_http_response(200, html))
    try:
        result = await WebService(schema_extractor=extractor).fetch(
            "https://example.com/r"
        )
    finally:
        patcher.stop()

    extractor.extract.assert_called_once_with("https://example.com/r", html)
    assert result["raw_content"] == "Ingrédients :\n- 1 pomme"
    assert result["title"] == "Titre page"  # repli sur le titre de la page
    assert result["images"] == ["https://ex.com/b.jpg", "https://ex.com/a.jpg"]


@pytest.mark.asyncio
async def test_fetch_raises_insufficient_content_on_js_site_without_schema():
    patcher = _patch_http(
        _http_response(200, "<html><body><div id='root'></div></body></html>")
    )
    try:
        with pytest.raises(InsufficientContentError, match="JavaScript"):
            await WebService().fetch("https://js-app.com")
    finally:
        patcher.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 404, 410])
async def test_fetch_raises_permanent_error_on_4xx(status):
    patcher = _patch_http(_http_response(status))
    try:
        with pytest.raises(PermanentFetchError, match=f"HTTP {status}"):
            await WebService().fetch("https://example.com/absente")
    finally:
        patcher.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_fetch_reraises_transient_http_error(status):
    patcher = _patch_http(_http_response(status))
    try:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await WebService().fetch("https://example.com")
    finally:
        patcher.stop()
    assert not isinstance(exc_info.value, PermanentFetchError)


@pytest.mark.asyncio
async def test_fetch_propagates_network_error():
    patcher = _patch_http(side_effect=httpx.ConnectError("refused"))
    try:
        with pytest.raises(httpx.ConnectError):
            await WebService().fetch("https://example.com")
    finally:
        patcher.stop()


@pytest.mark.parametrize(
    "status,expected",
    [
        (400, True),
        (403, True),
        (404, True),
        (410, True),
        (408, False),
        (425, False),
        (429, False),
        (500, False),
        (503, False),
    ],
)
def test_is_permanent_status(status, expected):
    assert WebService._is_permanent_status(status) is expected


def test_merge_images_dedupes_keeps_order_and_limits():
    first = ["https://ex.com/0.jpg"]
    others = [f"https://ex.com/{i}.jpg" for i in range(30)]
    merged = WebService._merge_images(first, others)
    assert merged[0] == "https://ex.com/0.jpg"
    assert len(merged) == 20
    assert len(set(merged)) == 20


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
