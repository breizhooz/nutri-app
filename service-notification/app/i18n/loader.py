import json
from pathlib import Path
from typing import Dict


class TranslationLoader:
    def __init__(self, locales_dir: Path = None):
        if locales_dir is None:
            self.locales_dir = Path(__file__).parent / "locales"
        else:
            self.locales_dir = locales_dir

        self.translations: Dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        if not self.locales_dir.exists():
            raise FileNotFoundError(f"Locales directory not found: {self.locales_dir}")

        for locale_file in self.locales_dir.glob("*.json"):
            locale = locale_file.stem
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    self.translations[locale] = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {locale_file}: {e}")
            except Exception as e:
                raise RuntimeError(f"Failed to load {locale_file}: {e}")

    def get(self, key: str, locale: str = "fr", **kwargs) -> str:
        keys = key.split(".")
        value = self.translations.get(locale, {})

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return key

        try:
            if isinstance(value, str):
                return value.format(**kwargs)
            return key
        except KeyError:
            return value


t = TranslationLoader()
