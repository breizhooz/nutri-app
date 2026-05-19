import re

import pytest

from app.services.spacy_extractor import SpacyExtractor


class TestSpacyExtractor:
    @pytest.fixture
    def extractor(self) -> SpacyExtractor:
        return SpacyExtractor()

    @pytest.mark.unit
    def test_quantity_re_is_class_attribute(self):
        """_QUANTITY_RE est un attribut de classe (re.Pattern)."""
        assert isinstance(SpacyExtractor._QUANTITY_RE, type(re.compile("")))

    @pytest.mark.unit
    def test_extract_empty_string_returns_empty_list(self, extractor):
        assert extractor.extract("") == []

    @pytest.mark.unit
    def test_extract_whitespace_only_returns_empty_list(self, extractor):
        assert extractor.extract("   ") == []

    @pytest.mark.unit
    def test_extract_simple_grammes(self, extractor):
        """'200g de farine de sarrasin' → 1 ingrédient, quantite=200, unite=g."""
        result = extractor.extract("200g de farine de sarrasin")
        assert result is not None
        assert len(result) == 1
        assert result[0].quantite == pytest.approx(200.0)
        assert result[0].unite == "g"
        assert "farine" in result[0].nom

    @pytest.mark.unit
    def test_extract_float_quantity_comma(self, extractor):
        """'2,5 cs d'huile' → quantite=2.5."""
        result = extractor.extract("2,5 cs d'huile d'olive")
        assert result is not None
        assert result[0].quantite == pytest.approx(2.5)
        assert result[0].unite == "cs"

    @pytest.mark.unit
    def test_extract_integer_no_unit(self, extractor):
        """'3 oeufs' → quantite=3, unite=g (défaut)."""
        result = extractor.extract("3 oeufs")
        assert result is not None
        assert result[0].quantite == pytest.approx(3.0)
        assert result[0].nom == "oeufs"

    @pytest.mark.unit
    def test_extract_multiline_returns_multiple(self, extractor):
        """3 lignes → 3 ingrédients."""
        text = "200g de farine\n3 oeufs\n50ml d'huile"
        result = extractor.extract(text)
        assert result is not None
        assert len(result) == 3

    @pytest.mark.unit
    def test_extract_no_quantity_returns_none(self, extractor):
        """Texte sans quantité → None."""
        result = extractor.extract("farine sarrasin huile")
        assert result is None

    @pytest.mark.unit
    def test_extract_confidence_in_valid_range(self, extractor):
        """confidence est dans [0, 1]."""
        result = extractor.extract("100g de sucre")
        assert result is not None
        assert 0.0 <= result[0].confidence <= 1.0

    @pytest.mark.unit
    def test_extract_preserves_raw_text(self, extractor):
        """raw_text == ligne originale."""
        line = "150g de beurre"
        result = extractor.extract(line)
        assert result is not None
        assert result[0].raw_text == line

    @pytest.mark.unit
    def test_extract_skips_empty_lines(self, extractor):
        """Lignes vides entre ingrédients ignorées."""
        text = "100g farine\n\n200ml lait"
        result = extractor.extract(text)
        assert result is not None
        assert len(result) == 2

    @pytest.mark.unit
    def test_spacy_load_failure_does_not_crash(self, extractor):
        """Si spaCy ne peut pas charger le modèle, extract() fonctionne quand même."""
        extractor._nlp = None
        result = extractor.extract("200g de sucre")
        assert result is not None