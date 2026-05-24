"""Tests unitaires pour CiqualXmlParser (parse_aliments, parse_compo, helpers)."""

import textwrap

import pytest

from app.services.ciqual_xml_parser import AlimRecord, CiqualXmlParser


def _write_xml(tmp_path, filename: str, content: str) -> str:
    path = tmp_path / filename
    path.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return str(tmp_path)


class TestFindXml:
    @pytest.mark.unit
    def test_finds_matching_file(self, tmp_path):
        (tmp_path / "alim_2024_01_01.xml").touch()
        assert CiqualXmlParser._find_xml(str(tmp_path), "alim_") == str(
            tmp_path / "alim_2024_01_01.xml"
        )

    @pytest.mark.unit
    def test_raises_when_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="alim_"):
            CiqualXmlParser._find_xml(str(tmp_path), "alim_")

    @pytest.mark.unit
    def test_does_not_match_wrong_prefix(self, tmp_path):
        (tmp_path / "compo_2024_01_01.xml").touch()
        with pytest.raises(FileNotFoundError):
            CiqualXmlParser._find_xml(str(tmp_path), "alim_")


class TestText:
    @pytest.mark.unit
    def test_returns_text(self):
        import xml.etree.ElementTree as ET

        el = ET.fromstring("<ROOT><name>Tomate</name></ROOT>")
        assert CiqualXmlParser._text(el, "name") == "Tomate"

    @pytest.mark.unit
    def test_returns_none_for_missing_tag(self):
        import xml.etree.ElementTree as ET

        el = ET.fromstring("<ROOT></ROOT>")
        assert CiqualXmlParser._text(el, "missing") is None

    @pytest.mark.unit
    def test_returns_none_for_empty_text(self):
        import xml.etree.ElementTree as ET

        el = ET.fromstring("<ROOT><name>   </name></ROOT>")
        assert CiqualXmlParser._text(el, "name") is None


class TestToFloat:
    @pytest.mark.unit
    def test_integer_value(self):
        assert CiqualXmlParser._to_float("100") == pytest.approx(100.0)

    @pytest.mark.unit
    def test_comma_decimal(self):
        assert CiqualXmlParser._to_float("13,5") == pytest.approx(13.5)

    @pytest.mark.unit
    def test_dot_decimal(self):
        assert CiqualXmlParser._to_float("13.5") == pytest.approx(13.5)

    @pytest.mark.unit
    def test_lt_prefix(self):
        assert CiqualXmlParser._to_float("<0.5") == pytest.approx(0.5)

    @pytest.mark.unit
    def test_dash_returns_none(self):
        assert CiqualXmlParser._to_float("-") is None

    @pytest.mark.unit
    def test_traces_returns_none(self):
        assert CiqualXmlParser._to_float("traces") is None

    @pytest.mark.unit
    def test_empty_returns_none(self):
        assert CiqualXmlParser._to_float("") is None

    @pytest.mark.unit
    def test_none_returns_none(self):
        assert CiqualXmlParser._to_float(None) is None

    @pytest.mark.unit
    def test_invalid_string_returns_none(self):
        assert CiqualXmlParser._to_float("n/a") is None


class TestParseAliments:
    _XML = """
        <?xml version="1.0"?>
        <ROOT>
          <ALIM>
            <alim_code>1001</alim_code>
            <alim_nom_fr>Tomate crue</alim_nom_fr>
            <alim_nom_eng>Raw tomato</alim_nom_eng>
            <alim_nom_sci>Solanum lycopersicum</alim_nom_sci>
            <alim_grp_code>GRP1</alim_grp_code>
          </ALIM>
          <ALIM>
            <alim_code>1002</alim_code>
            <alim_nom_fr>Beurre</alim_nom_fr>
            <alim_nom_eng>Butter</alim_nom_eng>
          </ALIM>
          <ALIM>
            <!-- pas de code → ignoré -->
          </ALIM>
        </ROOT>
    """

    @pytest.mark.unit
    def test_parse_returns_correct_count(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "alim_2024_01_01.xml", self._XML)
        records = CiqualXmlParser.parse_aliments(extract_dir)
        assert len(records) == 2

    @pytest.mark.unit
    def test_parse_record_fields(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "alim_2024_01_01.xml", self._XML)
        rec = CiqualXmlParser.parse_aliments(extract_dir)[1001]
        assert isinstance(rec, AlimRecord)
        assert rec.nom_fr == "Tomate crue"
        assert rec.nom_eng == "Raw tomato"
        assert rec.nom_sci == "Solanum lycopersicum"
        assert rec.alim_grp_code == "GRP1"

    @pytest.mark.unit
    def test_entry_without_code_is_skipped(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "alim_2024_01_01.xml", self._XML)
        records = CiqualXmlParser.parse_aliments(extract_dir)
        assert all(isinstance(k, int) for k in records)

    @pytest.mark.unit
    def test_optional_fields_none_when_absent(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "alim_2024_01_01.xml", self._XML)
        rec = CiqualXmlParser.parse_aliments(extract_dir)[1002]
        assert rec.nom_sci is None
        assert rec.alim_grp_code is None


class TestParseCompo:
    _XML = """
        <?xml version="1.0"?>
        <ROOT>
          <COMPO>
            <alim_code>2001</alim_code>
            <const_code>328</const_code>
            <teneur>18,5</teneur>
            <code_confiance>A</code_confiance>
          </COMPO>
          <COMPO>
            <alim_code>2001</alim_code>
            <const_code>25000</const_code>
            <teneur>1,2</teneur>
          </COMPO>
          <COMPO>
            <!-- const_code inconnu → ignoré -->
            <alim_code>2001</alim_code>
            <const_code>99999</const_code>
            <teneur>5,0</teneur>
          </COMPO>
          <COMPO>
            <!-- pas de alim_code → ignoré -->
            <const_code>328</const_code>
            <teneur>10,0</teneur>
          </COMPO>
        </ROOT>
    """

    @pytest.mark.unit
    def test_calories_parsed(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", self._XML)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert macros[2001]["calories"] == pytest.approx(18.5)

    @pytest.mark.unit
    def test_proteines_parsed(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", self._XML)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert macros[2001]["proteines"] == pytest.approx(1.2)

    @pytest.mark.unit
    def test_unknown_const_code_ignored(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", self._XML)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert len(macros) == 1

    @pytest.mark.unit
    def test_confidence_code_attached(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", self._XML)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert macros[2001]["code_confiance"] == "A"

    @pytest.mark.unit
    def test_missing_alim_code_ignored(self, tmp_path):
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", self._XML)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert 0 not in macros

    @pytest.mark.unit
    def test_trace_value_gives_none(self, tmp_path):
        xml = """
            <?xml version="1.0"?>
            <ROOT>
              <COMPO>
                <alim_code>3001</alim_code>
                <const_code>31000</const_code>
                <teneur>traces</teneur>
              </COMPO>
            </ROOT>
        """
        extract_dir = _write_xml(tmp_path, "compo_2024_01_01.xml", xml)
        macros = CiqualXmlParser.parse_compo(extract_dir)
        assert macros[3001]["glucides"] is None
