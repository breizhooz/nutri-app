import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ciqual_importer import CiqualImporter


def _write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = [
        "alim_code", "alim_nom_fr", "energie_kcal",
        "proteines_g", "glucides_g", "lipides_g", "fibres_g",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(code="1001", nom="Farine de sarrasin", energie="340", prot="13",
         gluc="71", lipid="3", fibres="6") -> dict:
    return {
        "alim_code": code, "alim_nom_fr": nom,
        "energie_kcal": energie, "proteines_g": prot,
        "glucides_g": gluc, "lipides_g": lipid, "fibres_g": fibres,
    }


class TestCiqualImporter:
    @pytest.fixture
    def mock_lookup(self) -> MagicMock:
        m = MagicMock()
        m.index_item = AsyncMock()
        return m

    @pytest.mark.unit
    def test_column_names_are_class_attributes(self):
        """Colonnes CSV définies comme attributs de classe."""
        assert CiqualImporter._COL_ID == "alim_code"
        assert CiqualImporter._COL_NOM_FR == "alim_nom_fr"
        assert CiqualImporter._COL_ENERGIE == "energie_kcal"

    @pytest.mark.unit
    async def test_import_valid_two_rows(self, db_session, mock_lookup, tmp_path):
        """CSV valide à 2 lignes → created=2, skipped=0."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("1001", "Farine sarrasin"), _row("1002", "Beurre")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        created, skipped = await importer.import_csv(p)

        assert created == 2
        assert skipped == 0
        assert mock_lookup.index_item.call_count == 2

    @pytest.mark.unit
    async def test_import_skips_row_without_name(self, db_session, mock_lookup, tmp_path):
        """Ligne sans nom → skipped."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("1001", "")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        created, skipped = await importer.import_csv(p)

        assert created == 0
        assert skipped == 1

    @pytest.mark.unit
    async def test_import_skips_row_without_code(self, db_session, mock_lookup, tmp_path):
        """Ligne sans code → skipped."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("", "Farine")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        _, skipped = await importer.import_csv(p)
        assert skipped == 1

    @pytest.mark.unit
    async def test_import_skips_duplicate_ciqual_id(self, db_session, mock_lookup, tmp_path):
        """Même ciqual_id au 2e import → skipped."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("9999", "Tomate")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        c1, s1 = await importer.import_csv(p)
        c2, s2 = await importer.import_csv(p)

        assert c1 == 1 and s1 == 0
        assert c2 == 0 and s2 == 1

    @pytest.mark.unit
    async def test_import_slug_generated_from_name(self, db_session, mock_lookup, tmp_path):
        """Le slug créé contient le nom slugifié."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("2001", "Poulet rôti")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        await importer.import_csv(p)

        from app.repositories.nutrition_item_repository import NutritionItemRepository
        item = await NutritionItemRepository(db_session).get_by_ciqual_id("2001")
        assert item is not None
        assert item.slug == "poulet-roti"

    @pytest.mark.unit
    async def test_import_comma_decimal_parsed(self, db_session, mock_lookup, tmp_path):
        """Valeur avec virgule décimale parsée correctement."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("3001", "Lait", energie="42,5", prot="3,3", gluc="4,8", lipid="1,2")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        await importer.import_csv(p)

        from app.repositories.nutrition_item_repository import NutritionItemRepository
        item = await NutritionItemRepository(db_session).get_by_ciqual_id("3001")
        assert item.calories == pytest.approx(42.5)

    @pytest.mark.unit
    async def test_import_indexes_each_created_item(self, db_session, mock_lookup, tmp_path):
        """index_item() appelé pour chaque item créé."""
        p = tmp_path / "ciqual.csv"
        _write_csv([_row("4001", "A"), _row("4002", "B"), _row("4003", "C")], p)

        importer = CiqualImporter(db_session, lookup=mock_lookup)
        await importer.import_csv(p)

        assert mock_lookup.index_item.call_count == 3


class TestCiqualParseFloat:
    @pytest.mark.unit
    def test_comma_decimal(self):
        assert CiqualImporter._parse_float("13,5") == pytest.approx(13.5)

    @pytest.mark.unit
    def test_lt_prefix(self):
        assert CiqualImporter._parse_float("<0.5") == pytest.approx(0.5)

    @pytest.mark.unit
    def test_dash_returns_zero(self):
        assert CiqualImporter._parse_float("-") == pytest.approx(0.0)

    @pytest.mark.unit
    def test_empty_returns_zero(self):
        assert CiqualImporter._parse_float("") == pytest.approx(0.0)

    @pytest.mark.unit
    def test_none_returns_zero(self):
        assert CiqualImporter._parse_float(None) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_traces_returns_zero(self):
        assert CiqualImporter._parse_float("traces") == pytest.approx(0.0)