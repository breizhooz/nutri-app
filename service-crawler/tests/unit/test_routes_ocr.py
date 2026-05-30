import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes.ocr import GroqExtractorFactory, OcrServiceFactory
from app.core.deps import get_token_payload
from app.main import app
from app.services.groq_recipe_extractor import ExtractedRecipe
from app.services.ocr_service import OcrError

_STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _extracted(is_recipe: bool = True, title: str = "Tarte aux pommes") -> ExtractedRecipe:
    return ExtractedRecipe(
        title=title,
        instructions="Mélanger puis cuire.",
        ingredients=[{"name": "pommes", "quantity": 3.0, "unit": "pièce"}],
        tokens_used=42,
        is_recipe=is_recipe,
        recipe_confidence=0.95,
    )


@pytest.fixture
def mock_ocr() -> MagicMock:
    ocr = MagicMock()
    ocr.extract_text_from_bytes = MagicMock(return_value="Tarte aux pommes\nPommes")
    return ocr


@pytest.fixture
def mock_extractor() -> AsyncMock:
    extractor = AsyncMock()
    extractor.extract = AsyncMock(return_value=_extracted())
    return extractor


@pytest.fixture
async def ocr_client(mock_ocr: MagicMock, mock_extractor: AsyncMock):
    app.dependency_overrides[OcrServiceFactory.inject] = lambda: mock_ocr
    app.dependency_overrides[GroqExtractorFactory.inject] = lambda: mock_extractor
    app.dependency_overrides[get_token_payload] = lambda: {
        "sub": str(_STUB_USER_ID),
        "type": "access",
        "user_admin": True,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, mock_ocr, mock_extractor
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ocr_scan_returns_extraction_without_enqueue(ocr_client):
    """Le scan analyse et renvoie l'extraction, mais n'enfile rien (revue avant décision)."""
    client, mock_ocr, mock_extractor = ocr_client
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("recipe.jpg", b"image-bytes", "image/jpeg")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_recipe"] is True
    assert body["title"] == "Tarte aux pommes"
    assert body["raw_text"] == "Tarte aux pommes\nPommes"
    mock_ocr.extract_text_from_bytes.assert_called_once_with(b"image-bytes")
    mock_extractor.extract.assert_awaited_once_with("Tarte aux pommes\nPommes")
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_import_enqueues_task(ocr_client):
    """L'import (décision explicite) enfile la création de la pré-recette."""
    client, _, _ = ocr_client
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr/import",
            json={"raw_text": "Tarte aux pommes\nPommes", "title": "Tarte aux pommes"},
        )

    assert resp.status_code == 202
    assert resp.json()["queued"] is True
    mock_task.delay.assert_called_once_with(
        user_id=str(_STUB_USER_ID),
        raw_text="Tarte aux pommes\nPommes",
        title="Tarte aux pommes",
    )


@pytest.mark.asyncio
async def test_ocr_import_rejects_empty_text(ocr_client):
    client, _, _ = ocr_client
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr/import",
            json={"raw_text": "   ", "title": "x"},
        )

    assert resp.status_code == 400
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_rejects_non_image(ocr_client):
    client, _, _ = ocr_client
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

    assert resp.status_code == 415
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_rejects_empty_file(ocr_client):
    client, _, _ = ocr_client
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("recipe.jpg", b"", "image/jpeg")},
        )

    assert resp.status_code == 400
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_rejects_too_large(ocr_client):
    client, _, _ = ocr_client
    big = b"x" * (10 * 1024 * 1024 + 1)
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("recipe.jpg", big, "image/jpeg")},
        )

    assert resp.status_code == 413
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_unreadable_image_returns_422(ocr_client):
    client, mock_ocr, _ = ocr_client
    mock_ocr.extract_text_from_bytes.side_effect = OcrError("illisible")
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("recipe.jpg", b"image-bytes", "image/jpeg")},
        )

    assert resp.status_code == 422
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_not_a_recipe_returns_raw_text(ocr_client):
    """Pas une recette : 200 + texte OCR brut, sans rien enfiler."""
    client, _, mock_extractor = ocr_client
    mock_extractor.extract.return_value = _extracted(is_recipe=False)
    with patch("app.api.routes.ocr.process_ocr_recipe") as mock_task:
        resp = await client.post(
            "/api/v1/crawler/ocr",
            files={"file": ("recipe.jpg", b"image-bytes", "image/jpeg")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_recipe"] is False
    assert body["raw_text"] == "Tarte aux pommes\nPommes"
    mock_task.delay.assert_not_called()
