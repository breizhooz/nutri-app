import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr_service import OcrError, OcrService


def _line(y, x_min=10, x_max=400, h=30):
    return [[x_min, y], [x_max, y], [x_max, y + h], [x_min, y + h]]


def _engine_returning(txts, boxes):
    return MagicMock(return_value=SimpleNamespace(txts=txts, boxes=boxes))


def test_extract_text_nominal():
    engine = _engine_returning(
        ("Tarte aux pommes", "Ingrédients: pommes"), [_line(10), _line(60)]
    )
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        text = OcrService().extract_text_from_bytes(b"img-bytes")

    assert text == "Tarte aux pommes\nIngrédients: pommes"
    # Le moteur reçoit directement les octets (aucun fichier temporaire).
    engine.assert_called_once_with(b"img-bytes")


def test_extract_text_strips_and_drops_blank_lines():
    engine = _engine_returning(
        ("  Gratin  ", "", "   ", "fromage"),
        [_line(10), _line(60), _line(110), _line(160)],
    )
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        text = OcrService().extract_text_from_bytes(b"img-bytes")

    assert text == "Gratin\nfromage"


def test_lines_are_put_in_reading_order():
    """Le service délègue l'ordre de lecture (colonnes) à ReadingOrder."""
    engine = _engine_returning(
        ("G0", "D0", "G1", "D1"),
        [
            _line(100, 50, 800),
            _line(100, 950, 1700),
            _line(160, 50, 800),
            _line(160, 950, 1700),
        ],
    )
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        text = OcrService().extract_text_from_bytes(b"img-bytes")

    assert text == "G0\nG1\nD0\nD1"


def test_empty_content_raises():
    with pytest.raises(OcrError):
        OcrService().extract_text_from_bytes(b"")


def test_nothing_detected_raises():
    engine = _engine_returning(None, None)
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        with pytest.raises(OcrError):
            OcrService().extract_text_from_bytes(b"img-bytes")


def test_only_blank_text_raises():
    engine = _engine_returning(("", "   "), [_line(10), _line(60)])
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        with pytest.raises(OcrError):
            OcrService().extract_text_from_bytes(b"img-bytes")


def test_large_image_is_downscaled_before_ocr():
    """Une grande image est ramenée à 2000 px max avant d'atteindre le moteur."""
    buf = io.BytesIO()
    Image.new("RGB", (4000, 1000), "white").save(buf, format="JPEG")

    captured: dict[str, bytes] = {}

    def _engine(content):
        captured["content"] = content
        return SimpleNamespace(txts=("x",), boxes=[_line(10)])

    with patch("app.services.ocr_service._get_engine", return_value=_engine):
        OcrService().extract_text_from_bytes(buf.getvalue())

    with Image.open(io.BytesIO(captured["content"])) as out:
        assert max(out.size) <= 2000


def test_engine_failure_raises_ocr_error():
    engine = MagicMock(side_effect=RuntimeError("decode failed"))
    with patch("app.services.ocr_service._get_engine", return_value=engine):
        with pytest.raises(OcrError):
            OcrService().extract_text_from_bytes(b"not-an-image")


def test_real_engine_reads_two_column_recipe_in_order():
    """Intégration : vrai moteur RapidOCR (ignoré s'il n'est pas installé)."""
    pytest.importorskip("rapidocr")
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.exists():  # police complète (œ, accents) requise
        pytest.skip("police DejaVu absente")
    font = ImageFont.truetype(str(font_path), 36)
    im = Image.new("RGB", (1800, 420), "white")
    draw = ImageDraw.Draw(im)
    for i, (left, right) in enumerate(
        [
            ("250 g de farine", "Mélangez la farine."),
            ("3 œufs entiers", "Ajoutez les œufs."),
            ("50 cl de lait", "Cuisez à 180 °C."),
        ]
    ):
        draw.text((60, 60 + 110 * i), left, fill="black", font=font)
        draw.text((1000, 60 + 110 * i), right, fill="black", font=font)
    buf = io.BytesIO()
    im.save(buf, format="PNG")

    lines = OcrService().extract_text_from_bytes(buf.getvalue()).splitlines()

    assert lines == [
        "250 g de farine",
        "3 œufs entiers",
        "50 cl de lait",  # colonne gauche d'abord…
        "Mélangez la farine.",
        "Ajoutez les œufs.",
        "Cuisez à 180 °C.",  # … puis colonne droite
    ]
