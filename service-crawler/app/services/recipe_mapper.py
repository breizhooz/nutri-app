import logging
import re
from dataclasses import dataclass

import httpx

from app.models.crawl_result import CrawlResult
from app.services.recipe_service_client import RecipeServiceClient

logger = logging.getLogger(__name__)


# ── Langue configuration ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class LanguageConfig:
    """Vocabulary used by IngredientParser for one language or a language group."""
    units: tuple[str, ...]       # regex patterns, longest-first to avoid partial matches
    connectors: tuple[str, ...]  # optional word linking quantity to name ("de", "of"…)
    default_unit: str            # label when no unit is detected in the line


FR_CONFIG = LanguageConfig(
    units=(
        r"cuill[eè]res?\s+[aà]\s+soupe",
        r"cuill[eè]res?\s+[aà]\s+dessert",
        r"cuill[eè]res?\s+[aà]\s+caf[eé]",
        r"tasses?", r"verres?", r"tranches?",
        r"gousses?", r"sachets?", r"bo[îi]tes?",
        r"pinc[eé]es?", r"filets?", r"brins?",
        r"feuilles?", r"morceaux?",
        r"kg", r"g", r"cl", r"dl", r"ml", r"l",
    ),
    connectors=(r"d[eu]\s+la\s+", r"d[eu]s?\s+", r"d'", r"de\s+"),
    default_unit="pièce",
)

EN_CONFIG = LanguageConfig(
    units=(
        r"tablespoons?", r"tbsps?\.?",
        r"teaspoons?", r"tsps?\.?",
        r"cups?", r"pints?", r"quarts?", r"gallons?",
        r"pounds?", r"lbs?\.?",
        r"ounces?", r"ozs?\.?",
        r"sticks?", r"cans?", r"jars?", r"bags?",
        r"slices?", r"cloves?", r"bunches?",
        r"handfuls?", r"pinches?", r"dashes?",
        r"kg", r"g", r"ml", r"l",
    ),
    connectors=(r"of\s+",),
    default_unit="piece",
)


def _merge(*configs: LanguageConfig, default_unit: str = "unit") -> LanguageConfig:
    """Build a combined config from multiple LanguageConfig, deduplicating and
    sorting unit patterns longest-first to avoid partial regex matches."""
    seen_units: list[str] = []
    seen_connectors: list[str] = []
    for cfg in configs:
        for u in cfg.units:
            if u not in seen_units:
                seen_units.append(u)
        for c in cfg.connectors:
            if c not in seen_connectors:
                seen_connectors.append(c)
    seen_units.sort(key=len, reverse=True)
    return LanguageConfig(
        units=tuple(seen_units),
        connectors=tuple(seen_connectors),
        default_unit=default_unit,
    )


MULTILINGUAL_CONFIG: LanguageConfig = _merge(FR_CONFIG, EN_CONFIG, default_unit="unit")


# ── Parser ────────────────────────────────────────────────────────────────────

@dataclass
class ParsedIngredient:
    name: str
    quantity: float
    unit: str


class IngredientParser:
    """
    Regex-based ingredient line parser.

    Accepts a LanguageConfig to adapt to FR, EN, or any combination.
    Defaults to MULTILINGUAL_CONFIG (FR + EN).

    Usage:
        parser = IngredientParser()                        # FR + EN
        parser = IngredientParser(config=FR_CONFIG)        # French only
        parser = IngredientParser(config=EN_CONFIG)        # English only
    """

    def __init__(self, config: LanguageConfig = MULTILINGUAL_CONFIG) -> None:
        self._config = config
        self._line_re = self._build_regex(config)

    @staticmethod
    def _build_regex(config: LanguageConfig) -> re.Pattern:
        unit_alt = "|".join(config.units)
        connector_alt = "|".join(config.connectors)
        return re.compile(
            r"^[\s\-•*]*"
            r"(?P<qty>\d+(?:[.,]\d+)?)\s*"
            r"(?:(?P<unit>" + unit_alt + r")\s*)?"
            r"(?:" + connector_alt + r")?"
            r"(?P<name>[A-Za-zÀ-ÖØ-öø-ÿœŒæÆ][^\d\n\r]{1,80}?)\s*$",
            re.IGNORECASE | re.MULTILINE,
        )

    def parse(self, text: str) -> list[ParsedIngredient]:
        seen: dict[str, ParsedIngredient] = {}
        for match in self._line_re.finditer(text):
            name = match.group("name").strip().rstrip(".,;:()")
            if not name or len(name) < 2:
                continue
            # Filtre les artefacts de backtracking regex (ex: "g x", "l a")
            if not any(len(w) >= 3 for w in name.split()):
                continue
            try:
                quantity = float(match.group("qty").replace(",", "."))
            except ValueError:
                quantity = 1.0
            raw_unit = match.group("unit") or ""
            unit = self._normalize_unit(raw_unit) if raw_unit else self._config.default_unit
            key = name.lower()
            if key not in seen:
                seen[key] = ParsedIngredient(name=name, quantity=quantity, unit=unit)
        return list(seen.values())

    @staticmethod
    def _normalize_unit(raw: str) -> str:
        """Lowercase and remove trailing plural 's' for single-word units."""
        unit = raw.strip().lower()
        if " " in unit:
            return unit  # multi-word units: "cuillère à soupe", "tablespoon" → unchanged
        if unit.endswith("s") and len(unit) > 2:
            return unit[:-1]
        return unit


# ── Mapper ────────────────────────────────────────────────────────────────────

class RecipeMapper:
    """Maps a validated CrawlResult to a recipe payload and sends it to service-recipe."""

    def __init__(
        self,
        recipe_client: RecipeServiceClient,
        parser: IngredientParser | None = None,
    ) -> None:
        self._recipe_client = recipe_client
        self._parser = parser or IngredientParser()  # MULTILINGUAL_CONFIG by default

    async def map_and_send(self, crawl_result: CrawlResult) -> dict:
        """Extract ingredients, resolve them in service-recipe, build and POST the recipe."""
        parsed = self._parser.parse(crawl_result.raw_content or "")
        recipe_ingredients = await self._resolve_ingredients(parsed)
        payload = self._build_payload(crawl_result, recipe_ingredients)
        return await self._recipe_client.create_recipe(payload)

    async def _resolve_ingredients(self, parsed: list[ParsedIngredient]) -> list[dict]:
        """Resolve each ingredient against service-recipe. Silently skips on error."""
        resolved: list[dict] = []
        for ingredient in parsed:
            try:
                ingredient_id = await self._recipe_client.get_or_create_ingredient(ingredient.name)
                resolved.append({
                    "ingredient_id": ingredient_id,
                    "quantity": ingredient.quantity,
                    "unit": ingredient.unit,
                })
            except (httpx.HTTPStatusError, httpx.RequestError):
                logger.warning(
                    "Skipping ingredient %r — service-recipe returned an error",
                    ingredient.name,
                )
        return resolved

    def _build_payload(self, crawl_result: CrawlResult, recipe_ingredients: list[dict]) -> dict:
        """Build the RecipeCreate-compatible dict from a CrawlResult."""
        return {
            "title": crawl_result.title or "Recette importée",
            "instructions": crawl_result.raw_content or "",
            "description": None,
            "source_url": crawl_result.url_origin,
            "image_url": crawl_result.images[0] if crawl_result.images else None,
            "recipe_ingredients": recipe_ingredients,
            "tags": {},
        }