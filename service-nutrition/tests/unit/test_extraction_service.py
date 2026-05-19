import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.extraction_service import ExtractionService
from app.services.lookup_service import LookupResult
from app.services.spacy_extractor import ExtractedIngredient

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _lookup_result(slug="farine-sarrasin") -> LookupResult:
    return LookupResult(
        slug=slug, nom_fr="Farine de sarrasin",
        calories=340.0, proteines=13.0, glucides=71.0, lipides=3.0,
        fibres=None, score=8.5,
    )


def _extracted(nom="farine") -> ExtractedIngredient:
    return ExtractedIngredient(
        raw_text="200g de farine", quantite=200.0, unite="g", nom=nom, confidence=0.75
    )


def _spacy(returns) -> MagicMock:
    m = MagicMock()
    m.extract = MagicMock(return_value=returns)
    return m


def _groq(returns=None, raises=None) -> MagicMock:
    m = MagicMock()
    if raises:
        m.extract = AsyncMock(side_effect=raises)
    else:
        m.extract = AsyncMock(return_value=returns or [])
    return m


def _lookup(returns) -> MagicMock:
    m = MagicMock()
    m.search = AsyncMock(return_value=returns)
    return m


def _mock_error(slug="err-slug") -> MagicMock:
    e = MagicMock()
    e.slug = slug
    return e


def _mock_repo(error_slug="err-slug") -> MagicMock:
    r = MagicMock()
    r.create = AsyncMock(return_value=_mock_error(error_slug))
    return r


class TestExtractionService:
    @pytest.mark.unit
    async def test_spacy_ok_groq_not_called(self, db_session):
        """spaCy réussit → Groq n'est jamais appelé."""
        spacy = _spacy([_extracted()])
        groq = _groq([])
        lookup = _lookup([_lookup_result()])

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=_mock_repo()):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["200g de farine"], USER_ID)

        groq.extract.assert_not_called()
        assert len(result.resolved) == 1
        assert len(result.failed) == 0

    @pytest.mark.unit
    async def test_spacy_none_groq_called(self, db_session):
        """spaCy retourne None → Groq appelé en fallback."""
        spacy = _spacy(None)
        groq = _groq([_extracted()])
        lookup = _lookup([_lookup_result()])

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=_mock_repo()):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["texte ambigu"], USER_ID)

        groq.extract.assert_called_once()
        assert len(result.resolved) == 1

    @pytest.mark.unit
    async def test_spacy_none_groq_raises_creates_macro_error(self, db_session):
        """spaCy None + Groq lève → MacroError créé."""
        spacy = _spacy(None)
        groq = _groq(raises=ValueError("groq boom"))
        lookup = _lookup([])
        repo = _mock_repo("gochujank-20260518")

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=repo):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["gochujank"], USER_ID)

        assert len(result.failed) == 1
        assert result.failed[0].macro_error_slug == "gochujank-20260518"
        assert result.failed[0].suggested is None

    @pytest.mark.unit
    async def test_spacy_ok_lookup_no_match_creates_macro_error(self, db_session):
        """spaCy extrait mais lookup vide → MacroError avec suggestion."""
        spacy = _spacy([_extracted("gochujank")])
        groq = _groq([])
        lookup = _lookup([])
        repo = _mock_repo("gochujank-err")

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=repo):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["gochujank"], USER_ID)

        assert len(result.failed) == 1
        assert result.failed[0].suggested == "gochujank"

    @pytest.mark.unit
    async def test_spacy_empty_groq_empty_creates_macro_error(self, db_session):
        """spaCy [] et Groq [] → MacroError (aucun ingrédient extrait)."""
        spacy = _spacy([])
        groq = _groq([])
        lookup = _lookup([])
        repo = _mock_repo("empty-err")

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=repo):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["texte vide"], USER_ID)

        assert len(result.failed) == 1

    @pytest.mark.unit
    async def test_unknown_unit_falls_back_to_raw_quantity(self, db_session):
        """Unité inconnue → grammes = quantité brute (pas None)."""
        spacy = _spacy([
            ExtractedIngredient(
                raw_text="3 oeufs", quantite=3.0, unite="oeuf", nom="oeuf", confidence=0.75
            )
        ])
        groq = _groq([])
        lookup = _lookup([_lookup_result("oeuf")])

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=_mock_repo()):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["3 oeufs"], USER_ID)

        assert len(result.resolved) == 1
        assert result.resolved[0].grammes == pytest.approx(3.0)

    @pytest.mark.unit
    async def test_mixed_resolved_and_failed(self, db_session):
        """2 ingrédients : 1 résolu + 1 échec → resolved=1, failed=1."""
        call_count = 0

        def spacy_side_effect(text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [_extracted("farine")]
            return None

        spacy = MagicMock()
        spacy.extract = MagicMock(side_effect=spacy_side_effect)
        groq = _groq(raises=ValueError("boom"))
        lookup = _lookup([_lookup_result()])
        repo = _mock_repo("fail-err")

        with patch("app.services.extraction_service.MacroErrorRepository", return_value=repo):
            svc = ExtractionService(db_session, spacy=spacy, groq=groq, lookup=lookup)
            result = await svc.process(["200g de farine", "gochujank"], USER_ID)

        assert len(result.resolved) == 1
        assert len(result.failed) == 1