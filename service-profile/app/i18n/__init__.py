"""Module i18n — exporte le singleton TranslationLoader."""
from app.i18n.loader import TranslationLoader

t = TranslationLoader()

__all__ = ["t"]