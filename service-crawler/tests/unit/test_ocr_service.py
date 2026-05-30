import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.ocr_service import OcrError, OcrService


def _reader_returning(lines):
    reader = MagicMock()
    reader.readtext = MagicMock(return_value=lines)
    return reader


def test_extract_text_nominal():
    reader = _reader_returning(["Tarte aux pommes", "Ingrédients: pommes"])
    with patch("app.services.ocr_service._get_reader", return_value=reader):
        text = OcrService().extract_text_from_bytes(b"img-bytes")

    assert text == "Tarte aux pommes\nIngrédients: pommes"
    # EasyOCR reçoit directement les octets (aucun fichier temporaire).
    reader.readtext.assert_called_once_with(b"img-bytes", detail=0, paragraph=True)


def test_extract_text_strips_and_drops_blank_lines():
    reader = _reader_returning(["  Gratin  ", "", "   ", "fromage"])
    with patch("app.services.ocr_service._get_reader", return_value=reader):
        text = OcrService().extract_text_from_bytes(b"img-bytes")

    assert text == "Gratin\nfromage"


def test_extract_text_uses_configured_langs():
    reader = _reader_returning(["texte"])
    with patch("app.services.ocr_service._get_reader", return_value=reader) as mock_get:
        OcrService(langs=("en",)).extract_text_from_bytes(b"img-bytes")

    mock_get.assert_called_once_with(("en",))


def test_empty_content_raises():
    with pytest.raises(OcrError):
        OcrService().extract_text_from_bytes(b"")


def test_no_text_extracted_raises():
    reader = _reader_returning(["", "   "])
    with patch("app.services.ocr_service._get_reader", return_value=reader):
        with pytest.raises(OcrError):
            OcrService().extract_text_from_bytes(b"img-bytes")


def test_large_image_is_downscaled_before_ocr():
    """Une grande image est ramenée à 2000 px max avant d'atteindre EasyOCR."""
    buf = io.BytesIO()
    Image.new("RGB", (4000, 1000), "white").save(buf, format="JPEG")

    captured: dict[str, bytes] = {}
    reader = MagicMock()
    reader.readtext = MagicMock(
        side_effect=lambda content, **_: captured.update(content=content) or ["x"]
    )
    with patch("app.services.ocr_service._get_reader", return_value=reader):
        OcrService().extract_text_from_bytes(buf.getvalue())

    with Image.open(io.BytesIO(captured["content"])) as out:
        assert max(out.size) <= 2000


def test_reader_failure_raises_ocr_error():
    reader = MagicMock()
    reader.readtext = MagicMock(side_effect=RuntimeError("decode failed"))
    with patch("app.services.ocr_service._get_reader", return_value=reader):
        with pytest.raises(OcrError):
            OcrService().extract_text_from_bytes(b"not-an-image")
