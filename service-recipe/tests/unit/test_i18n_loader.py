import pytest
from pathlib import Path
from app.i18n.loader import TranslationLoader

class TestTranslationLoader():
    """Test pour la classe TranslationLoader"""

    def test_load_all_translation(self, temp_locale_files):
        """Vérifie le chargement des fichiers de trad"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        # Assertions
        assert "fr" in loader.translations
        assert "en" in loader.translations
        assert loader.translations["fr"]["enums"]["difficulty"]["easy"] == "Facile"
        assert loader.translations["en"]["enums"]["difficulty"]["easy"] == "Easy"

    def test_get_simple_key_french(self, temp_locale_files, monkeypatch):
        """Récupere une clé du dict francais"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("enums.difficulty.easy", locale="fr")

        assert result == "Facile"

    def test_get_simple_key_english(self, temp_locale_files, monkeypatch):
        """Récupere une clé du dict anglais"""

        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("enums.difficulty.easy", locale="en")

        assert result == "Easy"

    def test_get_nested_key(self, temp_locale_files, monkeypatch):
        """Récupere une clé imbriquée"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("recipe.errors.not_found", locale="fr")

        assert result == "Recette non trouvée"

    def test_get_with_interpolation(self, temp_locale_files, monkeypatch):
        """Teste l'interpolation de variables"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get(
            "recipe.errors.validation",
            locale="fr",
            field="title"
        )

        assert result == "Le champ title est invalide"

    def test_get_missing_key_returns_key(self, temp_locale_files, monkeypatch):
        """Clé manquante retourne la clé elle-même (fallback)"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("nonexistent.key.path", locale="fr")
        assert result == "nonexistent.key.path"

    def test_get_missing_locale_returns_key(self, temp_locale_files, monkeypatch):
        """Locale inexistante retourne la clé (fallback)"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("enums.difficulty.easy", locale="de")  # Allemand non supporté

        assert result == "enums.difficulty.easy"

    def test_translate_enum_french(self, temp_locale_files, monkeypatch):
        """Teste translate_enum pour un enum en français"""
        loader = TranslationLoader(locales_dir=temp_locale_files)

        from enum import Enum

        class DifficultyLevel(str, Enum):
            EASY = "easy"
            MEDIUM = "medium"

        loader = TranslationLoader()
        result = loader.translate_enum(DifficultyLevel.EASY, "difficulty", locale="fr")

        assert result == "Facile"

    def test_default_locale_is_french(self, temp_locale_files, monkeypatch):
        """Par défaut, la locale est le français"""
        loader = TranslationLoader(locales_dir=temp_locale_files)
        result = loader.get("enums.difficulty.easy")  # Pas de locale spécifiée

        assert result == "Facile"

    def test_multiple_interpolations(self, temp_locale_files, monkeypatch):
        """Teste plusieurs variables d'interpolation"""

        loader = TranslationLoader(locales_dir=temp_locale_files)
        loader.translations["fr"]["test"] = {"multi": "{name} a {count} recettes"}

        result = loader.get("test.multi", locale="fr", name="Marie", count=5)

        assert result == "Marie a 5 recettes"