import json
from pathlib import Path

import pytest

from app.i18n.loader import TranslationLoader


class TestTranslationLoader:
    @pytest.fixture
    def loader(self) -> TranslationLoader:
        return TranslationLoader()

    @pytest.mark.unit
    def test_fr_locale_loaded(self, loader):
        """La locale 'fr' est chargée au démarrage."""
        assert "fr" in loader.translations

    @pytest.mark.unit
    def test_en_locale_loaded(self, loader):
        """La locale 'en' est chargée au démarrage."""
        assert "en" in loader.translations

    @pytest.mark.unit
    def test_get_simple_key_fr(self, loader):
        """Clé simple en français retourne la bonne traduction."""
        assert loader.get("subscription.not_found", locale="fr") == "Abonnement introuvable."

    @pytest.mark.unit
    def test_get_simple_key_en(self, loader):
        """Clé simple en anglais retourne la bonne traduction."""
        assert loader.get("subscription.not_found", locale="en") == "Subscription not found."

    @pytest.mark.unit
    def test_get_nested_key(self, loader):
        """Clé imbriquée sur 3 niveaux retourne la bonne traduction."""
        result = loader.get("errors.user_not_found", locale="fr")
        assert len(result) > 5
        assert result != "errors.user_not_found"

    @pytest.mark.unit
    def test_get_missing_key_returns_key_itself(self, loader):
        """Clé inexistante → retourne la clé elle-même (pas d'exception)."""
        result = loader.get("section.inexistante.cle", locale="fr")
        assert result == "section.inexistante.cle"

    @pytest.mark.unit
    def test_get_missing_locale_returns_key(self, loader):
        """Locale non chargée → retourne la clé elle-même."""
        result = loader.get("subscription.not_found", locale="es")
        assert result == "subscription.not_found"

    @pytest.mark.unit
    def test_get_with_interpolation(self, tmp_path):
        """Les kwargs sont interpolés dans la valeur traduite."""
        locales = tmp_path / "locales"
        locales.mkdir()
        (locales / "fr.json").write_text(
            json.dumps({"greet": "Bonjour {name}, vous avez {count} messages."}),
            encoding="utf-8",
        )
        loader = TranslationLoader(locales_dir=locales)
        result = loader.get("greet", locale="fr", name="Alice", count="3")
        assert result == "Bonjour Alice, vous avez 3 messages."

    @pytest.mark.unit
    def test_get_with_missing_kwargs_returns_raw_value(self, tmp_path):
        """kwargs manquants → retourne la valeur brute sans lever d'exception."""
        locales = tmp_path / "locales"
        locales.mkdir()
        (locales / "fr.json").write_text(
            json.dumps({"msg": "Bonjour {name}"}), encoding="utf-8"
        )
        loader = TranslationLoader(locales_dir=locales)
        result = loader.get("msg", locale="fr")
        assert result == "Bonjour {name}"

    @pytest.mark.unit
    def test_load_missing_directory_raises_file_not_found(self, tmp_path):
        """Dossier locales inexistant → FileNotFoundError au démarrage."""
        with pytest.raises(FileNotFoundError):
            TranslationLoader(locales_dir=tmp_path / "inexistant")

    @pytest.mark.unit
    def test_load_invalid_json_raises_value_error(self, tmp_path):
        """Fichier JSON malformé → ValueError au démarrage."""
        locales = tmp_path / "locales"
        locales.mkdir()
        (locales / "fr.json").write_text("{ invalid json }", encoding="utf-8")
        with pytest.raises(ValueError):
            TranslationLoader(locales_dir=locales)

    @pytest.mark.unit
    def test_get_returns_key_if_value_is_dict(self, tmp_path):
        """Clé qui pointe sur un dict (pas une string) → retourne la clé."""
        locales = tmp_path / "locales"
        locales.mkdir()
        (locales / "fr.json").write_text(
            json.dumps({"section": {"sub": "valeur"}}), encoding="utf-8"
        )
        loader = TranslationLoader(locales_dir=locales)
        # "section" pointe sur un dict → retourne la clé
        result = loader.get("section", locale="fr")
        assert result == "section"