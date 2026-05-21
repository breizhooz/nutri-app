import json
from pathlib import Path
from typing import Any


class TranslationLoader:
    def __init__(self, locales_dir: Path | None = None) -> None:
        self.locales_dir = locales_dir or Path(__file__).parent / "locales"
        self.translations: dict[str, Any] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.locales_dir.exists():
            raise FileNotFoundError(f"Locales directory not found: {self.locales_dir}")
        for locale_file in self.locales_dir.glob("*.json"):
            locale = locale_file.stem
            try:
                with open(locale_file, encoding="utf-8") as f:
                    self.translations[locale] = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {locale_file}: {e}")
            except Exception as e:
                raise RuntimeError(f"Failed to load {locale_file}: {e}")

    def get(self, key: str, locale: str = "fr", **kwargs) -> str:
        parts = key.split(".")
        value: Any = self.translations.get(locale, {})
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return key
        if not isinstance(value, str):
            return key
        try:
            return value.format(**kwargs) if kwargs else value
        except KeyError:
            return value

    def translate_enum(self, enum_value: Any, enum_type: str, locale: str = "fr") -> str:
        return self.get(f"enums.{enum_type}.{enum_value.value}", locale=locale)
