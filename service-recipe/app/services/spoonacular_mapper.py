"""Mappe un payload brut Spoonacular vers un ``RecipeImportItem``.

C'est ce ``RecipeImportItem`` qui est ensuite passé à
``RecipeService.create_full`` — le « process habituel » : résolution/création des
ingrédients, calcul des macros via service-nutrition, indexation Elasticsearch.
"""

import html
import re

from app.models.enums import CourseType, CuisineOrigin, DifficultyLevel, RecipeOrigin
from app.schemas.recipe_import import RecipeImportItem, RecipeIngredientImport

_TAG_RE = re.compile(r"<[^>]+>")

# dishTypes Spoonacular -> CourseType (premier match gagne).
_COURSE_BY_DISH_TYPE = {
    "dessert": CourseType.DESSERT,
    "beverage": CourseType.DRINK,
    "drink": CourseType.DRINK,
    "sauce": CourseType.SAUCE,
    "soup": CourseType.SOUP,
    "salad": CourseType.SALAD,
    "snack": CourseType.SNACK,
    "appetizer": CourseType.STARTER,
    "starter": CourseType.STARTER,
    "side dish": CourseType.SIDE_DISH,
    "breakfast": CourseType.BREAKFAST,
    "morning meal": CourseType.BREAKFAST,
    "brunch": CourseType.BREAKFAST,
    "main course": CourseType.MAIN_COURSE,
    "main dish": CourseType.MAIN_COURSE,
    "lunch": CourseType.MAIN_COURSE,
    "dinner": CourseType.MAIN_COURSE,
}

# cuisines Spoonacular -> CuisineOrigin.
_CUISINE_MAP = {
    "italian": CuisineOrigin.ITALIAN,
    "french": CuisineOrigin.FRENCH,
    "spanish": CuisineOrigin.SPANISH,
    "greek": CuisineOrigin.GREEK,
    "german": CuisineOrigin.GERMAN,
    "european": CuisineOrigin.EUROPE,
    "mediterranean": CuisineOrigin.EUROPE,
    "chinese": CuisineOrigin.CHINESE,
    "japanese": CuisineOrigin.JAPANESE,
    "thai": CuisineOrigin.THAI,
    "indian": CuisineOrigin.INDIAN,
    "korean": CuisineOrigin.KOREAN,
    "vietnamese": CuisineOrigin.VIETNAMESE,
    "asian": CuisineOrigin.ASIA,
    "african": CuisineOrigin.AFRICA,
    "moroccan": CuisineOrigin.MOROCCAN,
    "mexican": CuisineOrigin.MEXICAN,
    "american": CuisineOrigin.AMERICAN,
    "southern": CuisineOrigin.AMERICAN,
    "cajun": CuisineOrigin.AMERICAN,
    "creole": CuisineOrigin.AMERICAN,
    "bbq": CuisineOrigin.AMERICAN,
    "latin american": CuisineOrigin.SOUTH_AMERICA,
    "middle eastern": CuisineOrigin.MIDDLE_EAST,
    "jewish": CuisineOrigin.MIDDLE_EAST,
}


def strip_html(text: str | None) -> str:
    """Supprime les balises HTML et décode les entités d'un texte Spoonacular."""
    if not text:
        return ""
    no_tags = _TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def short_description(payload: dict, max_len: int = 280) -> str:
    """Description courte (résumé Spoonacular nettoyé, tronqué proprement)."""
    summary = strip_html(payload.get("summary"))
    if len(summary) <= max_len:
        return summary
    cut = summary[:max_len].rsplit(" ", 1)[0]
    return f"{cut}…"


def _instructions(payload: dict) -> str:
    """Texte des étapes : ``analyzedInstructions`` si présent, sinon HTML nettoyé."""
    analyzed = payload.get("analyzedInstructions") or []
    steps: list[str] = []
    for block in analyzed:
        for step in block.get("steps") or []:
            text = strip_html(step.get("step"))
            if text:
                steps.append(f"{len(steps) + 1}. {text}")
    if steps:
        return "\n".join(steps)
    return strip_html(payload.get("instructions"))


def _ingredients(payload: dict) -> list[RecipeIngredientImport]:
    out: list[RecipeIngredientImport] = []
    for raw in payload.get("extendedIngredients") or []:
        name = (raw.get("nameClean") or raw.get("name") or "").strip()
        if not name:
            continue
        # On privilégie les mesures métriques (cohérent avec une app FR).
        metric = (raw.get("measures") or {}).get("metric") or {}
        amount = metric.get("amount", raw.get("amount"))
        unit = metric.get("unitShort", raw.get("unit")) or ""
        try:
            quantity = float(amount) if amount is not None else 1.0
        except (TypeError, ValueError):
            quantity = 1.0
        out.append(
            RecipeIngredientImport(
                name=name[:200], quantity=quantity, unit=str(unit)[:50]
            )
        )
    return out


def _course_type(payload: dict) -> CourseType:
    for dish in payload.get("dishTypes") or []:
        course = _COURSE_BY_DISH_TYPE.get(str(dish).lower())
        if course is not None:
            return course
    return CourseType.MAIN_COURSE


def _cuisine_origin(payload: dict) -> CuisineOrigin:
    for cuisine in payload.get("cuisines") or []:
        origin = _CUISINE_MAP.get(str(cuisine).lower())
        if origin is not None:
            return origin
    return CuisineOrigin.AMERICAN


def _times(payload: dict) -> tuple[int | None, int | None]:
    """(prep, cook) en minutes. Spoonacular renvoie souvent -1 → None."""

    def _pos(value) -> int | None:
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    prep = _pos(payload.get("preparationMinutes"))
    cook = _pos(payload.get("cookingMinutes")) or _pos(payload.get("readyInMinutes"))
    return prep, cook


def spoonacular_to_import_item(payload: dict) -> RecipeImportItem:
    """Construit un ``RecipeImportItem`` à partir d'un payload Spoonacular brut."""
    prep, cook = _times(payload)
    try:
        servings = max(1, int(payload.get("servings") or 4))
    except (TypeError, ValueError):
        servings = 4

    return RecipeImportItem(
        title=(payload.get("title") or "Recette Spoonacular")[:300],
        description=short_description(payload) or None,
        instructions=_instructions(payload),
        prep_time_minutes=prep,
        cook_time_minutes=cook,
        servings=servings,
        difficulty=DifficultyLevel.EASY,
        cuisine_origin=_cuisine_origin(payload),
        origin_recipe=RecipeOrigin.WEB,
        course_type=_course_type(payload),
        free_tags=["spoonacular"],
        source_url=payload.get("sourceUrl") or payload.get("spoonacularSourceUrl"),
        image_url=payload.get("image"),
        ingredients=_ingredients(payload),
    )
