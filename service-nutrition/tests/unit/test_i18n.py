import json
from pathlib import Path

import pytest

from app.i18n.loader import TranslationLoader


@pytest.fixture
def loader(tmp_path) -> TranslationLoader:
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "fr.json").write_text(json.dumps({
        "nutrition_item": {
            "not_found": "Aliment introuvable.",
            "errors": {"invalid_macros": "Macros invalides."}
        },
        "greeting": "Bonjour {name} !",
        "errors": {"forbidden": "Accès refusé."},
    }), encoding="utf-8")
    (locales / "en.json").write_text(json.dumps({
        "nutrition_item": {"not_found": "Food not found."},
        "errors": {"forbidden": "Access denied."},
    }), encoding="utf-8")
    return TranslationLoader(locales_dir=locales)


class TestTranslationLoader:
    @pytest.mark.unit
    def test_get_simple_key_fr(self, loader):
        assert loader.get("errors.forbidden", locale="fr") == "Accès refusé."

    @pytest.mark.unit
    def test_get_simple_key_en(self, loader):
        assert loader.get("errors.forbidden", locale="en") == "Access denied."

    @pytest.mark.unit
    def test_get_nested_key(self, loader):
        assert loader.get("nutrition_item.not_found", locale="fr") == "Aliment introuvable."

    @pytest.mark.unit
    def test_get_deeply_nested_key(self, loader):
        assert loader.get("nutrition_item.errors.invalid_macros") == "Macros invalides."

    @pytest.mark.unit
    def test_get_unknown_key_returns_key(self, loader):
        assert loader.get("unknown.key") == "unknown.key"

    @pytest.mark.unit
    def test_get_unknown_locale_returns_key(self, loader):
        assert loader.get("errors.forbidden", locale="de") == "errors.forbidden"

    @pytest.mark.unit
    def test_get_with_format_kwargs(self, loader):
        result = loader.get("greeting", name="Alice")
        assert result == "Bonjour Alice !"

    @pytest.mark.unit
    def test_default_locale_is_fr(self, loader):
        assert loader.get("errors.forbidden") == "Accès refusé."

    @pytest.mark.unit
    def test_invalid_json_raises_value_error(self, tmp_path):
        locales = tmp_path / "bad"
        locales.mkdir()
        (locales / "fr.json").write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ValueError):
            TranslationLoader(locales_dir=locales)

    @pytest.mark.unit
    def test_missing_locales_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TranslationLoader(locales_dir=tmp_path / "nonexistent")