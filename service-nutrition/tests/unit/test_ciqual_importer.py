from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.ciqual_archive import CiqualArchive
from app.models.nutrition_item import NutritionItem
from app.services.ciqual_importer import CiqualImporter
from app.services.ciqual_xml_parser import AlimRecord, CiqualXmlParser


def _alim(code: int, nom_fr: str = "Tomate", nom_eng: str = "Tomato") -> AlimRecord:
    return AlimRecord(
        alim_code=code,
        nom_fr=nom_fr,
        nom_eng=nom_eng,
        nom_sci=None,
        alim_grp_code=None,
        alim_ssgrp_code=None,
        alim_ssssgrp_code=None,
    )


def _macros(**overrides) -> dict:
    base = {
        "calories": 20.0,
        "proteines": 1.0,
        "glucides": 4.0,
        "lipides": 0.2,
        "fibres": 1.2,
        "code_confiance": "A",
    }
    return {**base, **overrides}


def _patch_parser(aliments: dict, macros: dict):
    return (
        patch("app.services.ciqual_importer.CiqualXmlParser.parse_aliments", return_value=aliments),
        patch("app.services.ciqual_importer.CiqualXmlParser.parse_compo", return_value=macros),
    )


class TestCiqualImporter:
    @pytest.mark.unit
    async def test_import_archive_creates_items(self, db_session):
        """import_archive crée un NutritionItem par aliment."""
        aliments = {1001: _alim(1001, "Tomate"), 1002: _alim(1002, "Beurre")}
        macros = {1001: _macros(calories=20.0), 1002: _macros(calories=717.0)}

        pa, pc = _patch_parser(aliments, macros)
        with pa, pc:
            count = await CiqualImporter(db_session).import_archive("/fake", "sha1", "ciqual_2024_01_01.7z")

        assert count == 2

    @pytest.mark.unit
    async def test_import_archive_slug_includes_code(self, db_session):
        """Le slug généré contient le code aliment."""
        aliments = {2001: _alim(2001, "Poulet rôti")}
        macros = {2001: _macros()}

        pa, pc = _patch_parser(aliments, macros)
        with pa, pc:
            await CiqualImporter(db_session).import_archive("/fake", "sha2", "ciqual_2024_01_01.7z")

        result = await db_session.execute(
            select(NutritionItem).where(NutritionItem.ciqual_id == 2001)
        )
        item = result.scalar_one_or_none()
        assert item is not None
        assert "poulet" in item.slug
        assert "2001" in item.slug

    @pytest.mark.unit
    async def test_import_archive_updates_existing_item(self, db_session):
        """Un second import avec le même ciqual_id met à jour l'item."""
        aliments = {3001: _alim(3001, "Riz")}
        importer = CiqualImporter(db_session)

        pa, pc = _patch_parser(aliments, {3001: _macros(calories=130.0)})
        with pa, pc:
            await importer.import_archive("/fake", "sha3a", "ciqual_2024_01_01.7z")

        pa, pc = _patch_parser(aliments, {3001: _macros(calories=135.0)})
        with pa, pc:
            await importer.import_archive("/fake", "sha3b", "ciqual_2024_02_01.7z")

        result = await db_session.execute(
            select(NutritionItem).where(NutritionItem.ciqual_id == 3001)
        )
        item = result.scalar_one()
        assert item.calories == pytest.approx(135.0)

    @pytest.mark.unit
    async def test_import_archive_records_archive_entry(self, db_session):
        """import_archive enregistre une ligne dans ciqual_archives."""
        pa, pc = _patch_parser({}, {})
        with pa, pc:
            await CiqualImporter(db_session).import_archive("/fake", "sha-arc", "ciqual_2024_06_01.7z")

        result = await db_session.execute(
            select(CiqualArchive).where(CiqualArchive.sha256 == "sha-arc")
        )
        archive = result.scalar_one_or_none()
        assert archive is not None
        assert archive.version == "ciqual_2024_06_01"
        assert archive.item_count == 0

    @pytest.mark.unit
    async def test_already_imported_false_initially(self, db_session):
        assert await CiqualImporter(db_session).already_imported("unknown-sha") is False

    @pytest.mark.unit
    async def test_already_imported_true_after_import(self, db_session):
        pa, pc = _patch_parser({}, {})
        with pa, pc:
            await CiqualImporter(db_session).import_archive("/fake", "sha-known", "ciqual_2024_01_01.7z")

        assert await CiqualImporter(db_session).already_imported("sha-known") is True


class TestCiqualXmlParserToFloat:
    @pytest.mark.unit
    def test_comma_decimal(self):
        assert CiqualXmlParser._to_float("13,5") == pytest.approx(13.5)

    @pytest.mark.unit
    def test_lt_prefix(self):
        assert CiqualXmlParser._to_float("<0.5") == pytest.approx(0.5)

    @pytest.mark.unit
    def test_dash_returns_none(self):
        assert CiqualXmlParser._to_float("-") is None

    @pytest.mark.unit
    def test_empty_returns_none(self):
        assert CiqualXmlParser._to_float("") is None

    @pytest.mark.unit
    def test_none_returns_none(self):
        assert CiqualXmlParser._to_float(None) is None

    @pytest.mark.unit
    def test_traces_returns_none(self):
        assert CiqualXmlParser._to_float("traces") is None
