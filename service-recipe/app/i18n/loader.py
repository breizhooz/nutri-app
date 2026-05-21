from pathlib import Path

from nutri_shared.i18n.loader import TranslationLoader

t = TranslationLoader(locales_dir=Path(__file__).parent / "locales")

__all__ = ["t", "TranslationLoader"]
