"""Transforme openrecipes_fr.json (objets JSON concaténés, schema.org) vers le
format ``RecipeImportPayload`` attendu par ``scripts/import_recipes.py``.

Usage : python -m scripts.transform_openrecipes <source.json> <sortie.json> \
            [--user-id UUID]

Notes sur la donnée source (best-effort, la donnée d'origine est bruitée) :
- Le fichier n'est pas du NDJSON strict : ce sont des objets JSON concaténés,
  parfois multi-lignes, avec quelques enregistrements corrompus -> on les saute.
- La source ne contient PAS d'étapes de préparation -> ``instructions`` = "".
- Les macros ne sont pas fournies -> ``calories_per_100g`` & co restent à null ;
  c'est ``import_recipes`` qui les calcule via service-nutrition.
- Les quantités sont extraites au mieux du bloc texte ``ingredients`` ; à défaut
  on retombe sur une quantité par défaut (placeholder) à revoir avant prod.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import OrderedDict

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000000"

# Quantité/unité de repli quand on ne sait pas parser la ligne brute.
FALLBACK_QUANTITY = 1.0
FALLBACK_UNIT = "pièce"

# Garde-fous : un enregistrement avec 0 ou trop d'ingrédients est du bruit.
MIN_INGREDIENTS = 1
MAX_INGREDIENTS = 40

# recipeCategory (source) -> course_type (enum projet).
COURSE_BY_CATEGORY = {
    "salade": "enums.course_type.salad",
    "snack": "enums.course_type.snack",
    "petit déjeuner": "enums.course_type.breakfast",
    "dessert": "enums.course_type.dessert",
    "soupe": "enums.course_type.soup",
    "entrée": "enums.course_type.starter",
    "boisson": "enums.course_type.drink",
    "sauce": "enums.course_type.sauce",
}

# Unités reconnues dans le texte brut -> forme normalisée.
UNIT_LEXICON = [
    (r"cuill[èe]res?\s+à\s+soupe|c\.?\s*à\s*s\.?", "c. à soupe"),
    (r"cuill[èe]res?\s+à\s+caf[ée]|c\.?\s*à\s*c\.?", "c. à café"),
    (r"tasses?", "tasse"),
    (r"kilogrammes?|kg", "kg"),
    (r"grammes?|gr?\b", "g"),
    (r"millilitres?|ml", "ml"),
    (r"litres?|cl|dl|l\b", "l"),
    (r"livres?|lb", "livre"),
    (r"onces?|oz", "once"),
    (r"pinc[ée]es?", "pincée"),
    (r"gousses?", "gousse"),
    (r"tranches?", "tranche"),
    (r"sticks?", "stick"),
    (r"boîtes?", "boîte"),
    (r"sachets?", "sachet"),
    (r"verres?", "verre"),
    (r"poign[ée]es?", "poignée"),
]

# Durée ISO 8601 (PT#H#M).
_ISO_DUR = re.compile(r"P(?:T(?:(\d+)H)?(?:(\d+)M)?)?", re.IGNORECASE)
# Nombre en tête de ligne : "1-1/2", "1/2", "1.5", "1,5", "3".
_QTY = re.compile(r"^\s*[•\-\*]?\s*(\d+\s*-\s*\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)")


def parse_records(text: str) -> list[dict]:
    """Parse un flux d'objets JSON concaténés en sautant les corrompus."""
    dec = json.JSONDecoder()
    i, n, out = 0, len(text), []
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            obj, j = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            nxt = text.find("{", i + 1)
            if nxt < 0:
                break
            i = nxt
            continue
        if isinstance(obj, dict):
            out.append(obj)
        i = j
    return out


def iso_to_minutes(value) -> int | None:
    if not isinstance(value, str):
        return None
    m = _ISO_DUR.fullmatch(value.strip())
    if not m or not (m.group(1) or m.group(2)):
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    total = hours * 60 + minutes
    return total or None


def parse_servings(value) -> int:
    if isinstance(value, (int, float)):
        return max(1, int(value))
    if isinstance(value, str):
        m = re.search(r"\d+", value)
        if m:
            return max(1, int(m.group()))
    return 4


def _num(token: str) -> float:
    token = token.replace(" ", "")
    if "-" in token and "/" in token:  # "1-1/2"
        whole, frac = token.split("-", 1)
        num, den = frac.split("/")
        return float(whole) + float(num) / float(den)
    if "/" in token:
        num, den = token.split("/")
        return float(num) / float(den)
    return float(token.replace(",", "."))


def parse_qty_unit(line: str) -> tuple[float, str] | None:
    """Extrait (quantité, unité normalisée) du début d'une ligne d'ingrédient."""
    m = _QTY.match(line)
    if not m:
        return None
    try:
        qty = _num(m.group(1))
    except (ValueError, ZeroDivisionError):
        return None
    rest = line[m.end():].lstrip()
    unit = ""
    for pattern, norm in UNIT_LEXICON:
        if re.match(rf"(?:{pattern})\b", rest, re.IGNORECASE):
            unit = norm
            break
    return qty, unit or FALLBACK_UNIT


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def match_raw_line(name: str, raw_lines: list[str]) -> str | None:
    """Retrouve la ligne brute correspondant à un ingrédient nettoyé."""
    nname = _norm(name)
    if not nname:
        return None
    for line in raw_lines:
        if nname in _norm(line):
            return line
    # repli : mot significatif le plus long de l'ingrédient
    words = sorted((w for w in nname.split() if len(w) > 3), key=len, reverse=True)
    for w in words:
        for line in raw_lines:
            if w in _norm(line):
                return line
    return None


def clean_name(name) -> str:
    # Certaines sources fournissent un objet {name, quantity, ...} au lieu d'un
    # simple libellé -> on récupère son champ ``name``.
    if isinstance(name, dict):
        name = name.get("name", "")
    if not isinstance(name, str):
        return ""
    cleaned = re.sub(r"\s+", " ", name).strip()
    return cleaned[:200]


def transform(records: list[dict], user_id: str) -> dict:
    catalog: "OrderedDict[str, dict]" = OrderedDict()
    recipes: list[dict] = []
    seen_titles: set[str] = set()

    for rec in records:
        title = clean_name(rec.get("name") or "")
        cleaned = rec.get("ingredients_cleaned") or []
        if not title or not isinstance(cleaned, list):
            continue
        names = [clean_name(c) for c in cleaned if clean_name(str(c))]
        if not (MIN_INGREDIENTS <= len(names) <= MAX_INGREDIENTS):
            continue

        # dé-doublonnage des titres (slug unique en aval)
        key = _norm(title)
        if key in seen_titles:
            continue
        seen_titles.add(key)

        raw_block = rec.get("ingredients") or ""
        raw_lines = [l for l in re.split(r"[\n\r]+", str(raw_block)) if l.strip()]

        recipe_ings = []
        used_local: set[str] = set()
        for name in names:
            nkey = _norm(name)
            if not nkey or nkey in used_local:
                continue
            used_local.add(nkey)

            # catalogue global (clé normalisée, garde le 1er libellé rencontré)
            catalog.setdefault(
                nkey,
                {
                    "name": name,
                    "tags": [],
                    "free_tags": [],
                    "calories_per_100g": None,
                    "proteins_per_100g": None,
                    "carbs_per_100g": None,
                    "fats_per_100g": None,
                },
            )
            catalog_name = catalog[nkey]["name"]

            line = match_raw_line(name, raw_lines)
            parsed = parse_qty_unit(line) if line else None
            qty, unit = parsed if parsed else (FALLBACK_QUANTITY, FALLBACK_UNIT)
            recipe_ings.append(
                {"name": catalog_name, "quantity": round(qty, 2), "unit": unit}
            )

        if not recipe_ings:
            continue

        category = _norm(str(rec.get("recipeCategory") or ""))
        recipes.append(
            {
                "title": title[:300],
                "description": (rec.get("description") or None),
                "instructions": "",
                "prep_time_minutes": iso_to_minutes(rec.get("prepTime")),
                "cook_time_minutes": iso_to_minutes(rec.get("cookTime")),
                "servings": parse_servings(rec.get("recipeYield")),
                "difficulty": "enums.difficulty.easy",
                "cuisine_origin": "enums.origin_recipe.cuisine_origine.american",
                "origin_recipe": (
                    "enums.origin_recipe.web"
                    if rec.get("url")
                    else "enums.origin_recipe.personal"
                ),
                "course_type": COURSE_BY_CATEGORY.get(
                    category, "enums.course_type.main"
                ),
                "free_tags": [s for s in [rec.get("source")] if s],
                "book_name": None,
                "source_url": rec.get("url") or None,
                "image_url": rec.get("image") or None,
                "ingredients": recipe_ings,
            }
        )

    return {
        "created_by_user_id": user_id,
        "ingredients": list(catalog.values()),
        "recipes": recipes,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--user-id", default=DEFAULT_USER_ID)
    args = ap.parse_args()

    with open(args.source, "r", encoding="utf-8") as f:
        records = parse_records(f.read())

    payload = transform(records, args.user_id)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f"{len(records)} enregistrements lus -> "
        f"{len(payload['recipes'])} recette(s), "
        f"{len(payload['ingredients'])} ingrédient(s) au catalogue.\n"
        f"Écrit dans {args.output}"
    )


if __name__ == "__main__":
    main()
