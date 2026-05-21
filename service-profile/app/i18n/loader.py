"""Module d'internationalisation — chargement et résolution des traductions."""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TranslationLoader:
    """Charge les fichiers JSON de localisation et résout les clés en notation pointée.

    Exemple : t.get("profile.not_found", "fr") → "Profil introuvable"
    Fallback automatique vers 'fr' si la locale demandée est absente.
    """

    def __init__(self) -> None:
        """Initialise le loader et charge toutes les locales disponibles."""
        self._locales: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Charge tous les fichiers *.json depuis le répertoire locales/."""
        locales_dir = Path(__file__).parent / "locales"
        for path in locales_dir.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                self._locales[path.stem] = json.load(f)
            logger.debug("Locale '%s' chargée", path.stem)

    def get(self, key: str, locale: str = "fr") -> str:
        """Résout une clé en notation pointée dans la locale demandée.

        Retourne la clé brute si la traduction est introuvable.
        """
        parts = key.split(".")
        data: Any = self._locales.get(locale, self._locales.get("fr", {}))
        for part in parts:
            if isinstance(data, dict):
                data = data.get(part, key)
            else:
                return key
        return str(data) if not isinstance(data, dict) else key


t = TranslationLoader()