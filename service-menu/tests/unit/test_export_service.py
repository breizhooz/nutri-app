import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.export_service import export_shopping_list, _to_csv, _to_pdf
from app.schemas.shopping_list import ShoppingList, ShoppingItem


@pytest.fixture
def mock_weasyprint():
    mock_module = MagicMock()
    mock_module.HTML.return_value.write_pdf.return_value = b"fake-pdf-content"
    with patch.dict("sys.modules", {"weasyprint": mock_module}):
        yield mock_module.HTML


async def _read(response) -> str:
    parts = []
    async for chunk in response.body_iterator:
        parts.append(chunk if isinstance(chunk, str) else chunk.decode())
    return "".join(parts)


def _make_sl(**overrides) -> ShoppingList:
    defaults = dict(
        menu_id=1, menu_slug="test-menu", nb_persons=2, start_date=date(2026, 1, 6),
        items=[
            ShoppingItem(ingredient_id=1, ingredient_name="Pasta", total_quantity=400.0, unit="g",    category="grain"),
            ShoppingItem(ingredient_id=2, ingredient_name="Egg",   total_quantity=6.0,   unit="unit", category=None),
        ],
    )
    defaults.update(overrides)
    return ShoppingList(**defaults)


class TestCsvExport:
    def test_media_type_is_text_csv(self):
        assert _to_csv(_make_sl()).media_type == "text/csv"

    def test_content_disposition_contains_menu_id(self):
        assert "shopping-list-42.csv" in _to_csv(_make_sl(menu_id=42)).headers["content-disposition"]

    async def test_header_row_present(self):
        content = await _read(_to_csv(_make_sl()))
        for col in ("Ingrédient", "Quantité", "Unité", "Catégorie"):
            assert col in content

    async def test_ingredient_data_rows_present(self):
        content = await _read(_to_csv(_make_sl()))
        assert "Pasta" in content
        assert "400.0" in content
        assert "grain" in content

    async def test_empty_category_written_as_blank(self):
        content = await _read(_to_csv(_make_sl()))
        lines = content.strip().splitlines()
        egg_line = next(l for l in lines if "Egg" in l)
        assert egg_line.endswith(",")

    async def test_row_count_matches_items(self):
        sl = _make_sl()
        content = await _read(_to_csv(sl))
        assert len(content.strip().splitlines()[1:]) == len(sl.items)


class TestPdfExport:
    def test_media_type_is_application_pdf(self, mock_weasyprint):
        assert _to_pdf(_make_sl()).media_type == "application/pdf"

    def test_content_disposition_contains_menu_id(self, mock_weasyprint):
        assert "shopping-list-7.pdf" in _to_pdf(_make_sl(menu_id=7)).headers["content-disposition"]

    async def test_pdf_body_is_non_empty(self, mock_weasyprint):
        parts = []
        async for chunk in _to_pdf(_make_sl()).body_iterator:
            parts.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        assert b"".join(parts)


class TestExportDispatch:
    def test_csv_format_returns_csv_response(self):
        assert export_shopping_list(_make_sl(), "csv").media_type == "text/csv"

    def test_pdf_format_returns_pdf_response(self, mock_weasyprint):
        assert export_shopping_list(_make_sl(), "pdf").media_type == "application/pdf"