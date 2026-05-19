import pytest

from app.services.unit_converter import UnitConverter


class TestUnitConverter:
    @pytest.mark.unit
    def test_common_units_class_attribute(self):
        """_COMMON est un attribut de classe non vide."""
        assert isinstance(UnitConverter._COMMON, dict)
        assert "g" in UnitConverter._COMMON
        assert "kg" in UnitConverter._COMMON

    @pytest.mark.unit
    async def test_grammes_passthrough(self, db_session):
        assert await UnitConverter(db_session).to_grammes(200.0, "g") == pytest.approx(200.0)

    @pytest.mark.unit
    async def test_kilogrammes(self, db_session):
        assert await UnitConverter(db_session).to_grammes(0.5, "kg") == pytest.approx(500.0)

    @pytest.mark.unit
    async def test_millilitres(self, db_session):
        assert await UnitConverter(db_session).to_grammes(100.0, "ml") == pytest.approx(100.0)

    @pytest.mark.unit
    async def test_litres(self, db_session):
        assert await UnitConverter(db_session).to_grammes(1.5, "l") == pytest.approx(1500.0)

    @pytest.mark.unit
    async def test_centilitres(self, db_session):
        assert await UnitConverter(db_session).to_grammes(5.0, "cl") == pytest.approx(50.0)

    @pytest.mark.unit
    async def test_decilitres(self, db_session):
        assert await UnitConverter(db_session).to_grammes(2.0, "dl") == pytest.approx(200.0)

    @pytest.mark.unit
    async def test_case_insensitive_g(self, db_session):
        assert await UnitConverter(db_session).to_grammes(100.0, "G") == pytest.approx(100.0)

    @pytest.mark.unit
    async def test_case_insensitive_kg(self, db_session):
        assert await UnitConverter(db_session).to_grammes(1.0, "KG") == pytest.approx(1000.0)

    @pytest.mark.unit
    async def test_unknown_unit_found_in_db(self, db_session):
        """Unité inconnue mais présente en DB → conversion correcte."""
        from app.repositories.unit_conversion_repository import UnitConversionRepository
        await UnitConversionRepository(db_session).create(
            unite="cs", grammes=10.0, note="cuillère à soupe"
        )
        result = await UnitConverter(db_session).to_grammes(3.0, "cs")
        assert result == pytest.approx(30.0)

    @pytest.mark.unit
    async def test_specific_aliment_type_takes_priority(self, db_session):
        """Conversion spécifique à l'aliment prioritaire sur universelle."""
        from app.repositories.unit_conversion_repository import UnitConversionRepository
        repo = UnitConversionRepository(db_session)
        await repo.create(unite="cs", grammes=10.0)
        await repo.create(unite="cs", grammes=15.0, aliment_type="farine")

        result = await UnitConverter(db_session).to_grammes(1.0, "cs", aliment_type="farine")
        assert result == pytest.approx(15.0)

    @pytest.mark.unit
    async def test_universal_fallback_when_no_specific(self, db_session):
        """Sans conversion spécifique → fallback sur universelle."""
        from app.repositories.unit_conversion_repository import UnitConversionRepository
        await UnitConversionRepository(db_session).create(unite="cs", grammes=10.0)

        result = await UnitConverter(db_session).to_grammes(2.0, "cs", aliment_type="huile")
        assert result == pytest.approx(20.0)

    @pytest.mark.unit
    async def test_totally_unknown_unit_returns_none(self, db_session):
        """Unité absente de _COMMON et de la DB → None."""
        result = await UnitConverter(db_session).to_grammes(2.0, "bol")
        assert result is None