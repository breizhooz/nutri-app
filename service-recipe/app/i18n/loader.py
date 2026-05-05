import json
from pathlib import Path
from typing import Any, Dict, List, Union

class TranslationLoader:
    def __init__(self, locales_dir: Path = None):
        if locales_dir is None:
            self.locales_dir = Path(__file__).parent / "locales"
        else:
            self.locales_dir = locales_dir

        self.translations: Dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Load all available translations on start"""
        for locale_dir in self.locales_dir.glob("*.json"):
            locale = locale_dir.stem #get filename without extension
            with open(locale_dir, "r", encoding="utf-8") as f:
                self.translations[locale] = json.load(f)

    def get(self, key: str, locale: str = "fr", **kwargs) -> str:
        """
        Récupère une traduction

        Args:
            key: Clé au format "section.subsection.key" ou "enums.difficulty.facile"
            locale: Code langue (fr, en, es...)
            **kwargs: Variables pour interpolation {var}

        Exemples:
            t.get("enums.difficulty.facile", locale="en")  # "Easy"
            t.get("recipe.errors.not_found", locale="fr")  # "Recette non trouvée"
        """
        keys = key.split(".")
        value = self.translations.get(locale, {})

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Si on ne trouve pas la clé ou si on n'est plus dans un dict
                # On retourne la clé d'origine comme fallback immédiat
                return key

            # Si on arrive ici, value est normalement la chaîne traduite
            # On gère l'interpolation des variables si nécessaire
        try:
            if isinstance(value, str):
                return value.format(**kwargs)
            return key  # Au cas où la clé pointe vers un dictionnaire complet
        except KeyError:
            return value  # Retourne la string brute si une variable d'interpolation manque

    def translate_enum(self, enum_value, enum_type: str, locale: str = "fr") -> str:
        """Helper spécifique pour les enums"""
        return self.get(f"enums.{enum_type}.{enum_value.value}", locale=locale)


# Instance globale
t = TranslationLoader()