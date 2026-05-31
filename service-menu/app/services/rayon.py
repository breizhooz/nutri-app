"""Assign an ingredient to a coarse store aisle ("rayon") for the shopping list.

Two signals, in order of trust:

1. **Tags** — an ingredient's ``tags`` may contain a ``TypeOfIngredient`` value.
   Sub-types (yogurt, cheese…) are folded into their parent aisle (dairy…).
2. **Name** — most ingredients carry no type tag (they are created on the fly
   from recipes), so we fall back to matching the French name against a keyword
   lexicon (banane → fruits, skyr → produits laitiers…).

The output rayons are exactly the keys the frontend (``CATEGORY_META``) and the
CSV/PDF export already understand.
"""

import re
import unicodedata

from app.models.enums.food import TypeOfIngredient as T

_PREFIX = "enums.type_of_ingredient."

# Coarse rayons. "drink" and "other" have no matching enum member.
RAYON_MEAT = T.MEAT.value
RAYON_FISH = T.FISH.value
RAYON_EGG = T.EGG.value
RAYON_DAIRY = T.DAIRY.value
RAYON_FRUIT = T.FRUIT.value
RAYON_VEGETABLE = T.VEGETABLE.value
RAYON_LEGUME = T.LEGUME.value
RAYON_GRAIN = T.GRAIN.value
RAYON_FAT = T.FAT.value
RAYON_HERB = T.HERB.value
RAYON_CONDIMENT = T.CONDIMENT.value
RAYON_DRINK = "enums.type_of_ingredient.drink"
RAYON_OTHER = "enums.type_of_ingredient.other"

# ── 1. Tag → rayon ────────────────────────────────────────────────────────────
_FAMILIES: dict[str, tuple[T, ...]] = {
    RAYON_MEAT: (T.MEAT, T.WHITE_MEAT, T.RED_MEAT, T.PROCESSED_MEAT),
    RAYON_FISH: (
        T.FISH,
        T.WHITE_FISH,
        T.FATTY_FISH,
        T.SMOKED_FISH,
        T.SEAFOOD,
        T.CRUSTACEAN,
        T.MOLLUSC,
    ),
    RAYON_EGG: (T.EGG,),
    RAYON_DAIRY: (T.DAIRY, T.MILK, T.CHEESE, T.YOGURT, T.BUTTER, T.CREAM),
    RAYON_FRUIT: (T.FRUIT, T.CITRUS, T.BERRY, T.TROPICAL_FRUIT, T.DRIED_FRUIT),
    RAYON_VEGETABLE: (
        T.VEGETABLE,
        T.LEAFY_VEGETABLE,
        T.ROOT_VEGETABLE,
        T.BULB_VEGETABLE,
        T.STEM_VEGETABLE,
        T.FLOWER_VEGETABLE,
        T.FRUIT_VEGETABLE,
    ),
    RAYON_LEGUME: (T.LEGUME,),
    RAYON_GRAIN: (T.GRAIN, T.PSEUDO_GRAIN, T.PASTA, T.RICE, T.FLOUR),
    RAYON_FAT: (T.FAT, T.OIL, T.MARGARINE),
    RAYON_HERB: (T.HERB, T.SPICE),
    RAYON_CONDIMENT: (T.CONDIMENT, T.SAUCE, T.VINEGAR, T.MUSTARD),
    RAYON_DRINK: (
        T.BEVERAGE,
        T.WATER,
        T.JUICE,
        T.SODA,
        T.HOT_DRINK,
        T.COFFEE,
        T.TEA,
        T.INFUSION,
        T.ALCOHOL,
        T.WINE,
        T.BEER,
        T.SPIRIT,
    ),
}
_TYPE_TO_RAYON: dict[str, str] = {
    member.value: rayon for rayon, members in _FAMILIES.items() for member in members
}


def rayon_from_tags(tags: list[str]) -> str | None:
    """Coarse aisle from the first ``TypeOfIngredient`` tag, or ``None``."""
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if tag in _TYPE_TO_RAYON:
            return _TYPE_TO_RAYON[tag]
        if tag.startswith(_PREFIX):
            return RAYON_OTHER
    return None


# ── 2. Name → rayon (French keyword lexicon) ──────────────────────────────────
# Multi-word phrases are matched first (whole-phrase) so e.g. "pomme de terre"
# (légume) wins over the single word "pomme" (fruit).
_NAME_PHRASES: list[tuple[str, str]] = [
    ("pomme de terre", RAYON_VEGETABLE),
    ("patate douce", RAYON_VEGETABLE),
    ("haricot vert", RAYON_VEGETABLE),
    ("petit pois", RAYON_VEGETABLE),
    ("chou fleur", RAYON_VEGETABLE),
    ("chou rouge", RAYON_VEGETABLE),
    ("noix de saint jacques", RAYON_FISH),
    ("saint jacques", RAYON_FISH),
    ("fruit de mer", RAYON_FISH),
    ("filet de poisson", RAYON_FISH),
    ("fromage blanc", RAYON_DAIRY),
    ("petit suisse", RAYON_DAIRY),
    ("creme fraiche", RAYON_DAIRY),
    ("lait de coco", RAYON_OTHER),
    ("noix de coco", RAYON_OTHER),
    ("blanc de poulet", RAYON_MEAT),
    ("cuisse de poulet", RAYON_MEAT),
    ("pois chiche", RAYON_LEGUME),
    ("haricot rouge", RAYON_LEGUME),
    ("haricot blanc", RAYON_LEGUME),
    ("haricot noir", RAYON_LEGUME),
    ("huile d olive", RAYON_FAT),
    ("huile de tournesol", RAYON_FAT),
    ("sauce soja", RAYON_CONDIMENT),
    ("concentre de tomate", RAYON_CONDIMENT),
]

_NAME_WORDS: dict[str, list[str]] = {
    RAYON_FRUIT: [
        "pomme",
        "banane",
        "poire",
        "orange",
        "citron",
        "clementine",
        "mandarine",
        "pamplemousse",
        "fraise",
        "framboise",
        "myrtille",
        "mure",
        "cassis",
        "raisin",
        "peche",
        "abricot",
        "nectarine",
        "prune",
        "cerise",
        "kiwi",
        "ananas",
        "mangue",
        "papaye",
        "melon",
        "pasteque",
        "figue",
        "datte",
        "grenade",
        "litchi",
        "kaki",
        "coing",
        "avocat",
        "fruit",
    ],
    RAYON_VEGETABLE: [
        "tomate",
        "carotte",
        "courgette",
        "aubergine",
        "poivron",
        "oignon",
        "ail",
        "echalote",
        "poireau",
        "brocoli",
        "chou",
        "epinard",
        "salade",
        "laitue",
        "mache",
        "roquette",
        "concombre",
        "radis",
        "navet",
        "betterave",
        "celeri",
        "fenouil",
        "mais",
        "champignon",
        "patate",
        "potiron",
        "courge",
        "butternut",
        "potimarron",
        "citrouille",
        "asperge",
        "artichaut",
        "endive",
        "cresson",
        "blette",
        "panais",
        "legume",
    ],
    RAYON_MEAT: [
        "boeuf",
        "veau",
        "porc",
        "agneau",
        "mouton",
        "poulet",
        "dinde",
        "canard",
        "lapin",
        "jambon",
        "lardon",
        "bacon",
        "saucisse",
        "saucisson",
        "steak",
        "viande",
        "escalope",
        "merguez",
        "chipolata",
        "boudin",
        "volaille",
        "gigot",
        "roti",
        "charcuterie",
        "chorizo",
        "entrecote",
        "magret",
        "hache",
    ],
    RAYON_FISH: [
        "poisson",
        "saumon",
        "thon",
        "cabillaud",
        "colin",
        "merlu",
        "sole",
        "dorade",
        "truite",
        "sardine",
        "maquereau",
        "hareng",
        "anchois",
        "crevette",
        "gambas",
        "moule",
        "huitre",
        "crabe",
        "homard",
        "langoustine",
        "calamar",
        "encornet",
        "poulpe",
        "seiche",
        "surimi",
        "lotte",
        "raie",
        "espadon",
        "haddock",
    ],
    RAYON_DAIRY: [
        "lait",
        "yaourt",
        "yogourt",
        "skyr",
        "fromage",
        "creme",
        "beurre",
        "mascarpone",
        "ricotta",
        "mozzarella",
        "parmesan",
        "gruyere",
        "emmental",
        "comte",
        "cheddar",
        "feta",
        "chevre",
        "brie",
        "camembert",
        "faisselle",
        "kefir",
        "raclette",
    ],
    RAYON_EGG: ["oeuf"],
    RAYON_GRAIN: [
        "pates",
        "spaghetti",
        "macaroni",
        "penne",
        "tagliatelle",
        "nouille",
        "riz",
        "semoule",
        "boulgour",
        "quinoa",
        "farine",
        "pain",
        "baguette",
        "biscotte",
        "ble",
        "avoine",
        "flocon",
        "couscous",
        "polenta",
        "orge",
        "epeautre",
        "seigle",
        "gnocchi",
        "lasagne",
        "chapelure",
        "cereale",
        "muesli",
    ],
    RAYON_LEGUME: [
        "lentille",
        "feve",
        "flageolet",
        "soja",
        "tofu",
        "edamame",
        "haricot",
    ],
    RAYON_FAT: ["huile", "margarine", "graisse", "saindoux"],
    RAYON_HERB: [
        "persil",
        "basilic",
        "coriandre",
        "thym",
        "romarin",
        "menthe",
        "ciboulette",
        "aneth",
        "estragon",
        "laurier",
        "origan",
        "sauge",
        "epice",
        "cumin",
        "curcuma",
        "paprika",
        "cannelle",
        "muscade",
        "gingembre",
        "curry",
        "herbe",
        "safran",
        "piment",
        "poivre",
        "sel",
        "vanille",
        "cardamome",
        "aromate",
    ],
    RAYON_CONDIMENT: [
        "moutarde",
        "ketchup",
        "mayonnaise",
        "mayo",
        "sauce",
        "vinaigre",
        "vinaigrette",
        "tabasco",
        "harissa",
        "pesto",
        "tapenade",
        "cornichon",
        "olive",
        "capre",
        "bouillon",
        "miso",
        "tahini",
    ],
    RAYON_DRINK: [
        "eau",
        "jus",
        "vin",
        "biere",
        "soda",
        "cola",
        "limonade",
        "cafe",
        "boisson",
        "champagne",
        "cidre",
        "rhum",
        "vodka",
        "whisky",
        "sirop",
    ],
    RAYON_OTHER: [
        "sucre",
        "miel",
        "chocolat",
        "cacao",
        "confiture",
        "nutella",
        "bonbon",
        "levure",
        "bicarbonate",
        "gelatine",
        "agar",
        "noix",
        "noisette",
        "amande",
        "cacahuete",
        "pistache",
        "graine",
        "sesame",
        "cajou",
        "glace",
    ],
}
_WORD_TO_RAYON: dict[str, str] = {
    word: rayon for rayon, words in _NAME_WORDS.items() for word in words
}


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse non-letters to single spaces."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z]+", " ", text).strip()


def rayon_from_name(name: str) -> str | None:
    """Best-effort coarse aisle guessed from a French ingredient name."""
    norm = _normalize(name)
    if not norm:
        return None
    padded = f" {norm} "
    for phrase, rayon in _NAME_PHRASES:
        if f" {phrase} " in padded:
            return rayon
    for token in norm.split():
        if token in _WORD_TO_RAYON:
            return _WORD_TO_RAYON[token]
        # naive singular (tomates → tomate, oeufs → oeuf)
        if token.endswith("s") and len(token) > 3 and token[:-1] in _WORD_TO_RAYON:
            return _WORD_TO_RAYON[token[:-1]]
    return None


def category_to_rayon(tags: list[str], name: str = "") -> str | None:
    """Coarse aisle for an ingredient: trust its type tag, else guess by name."""
    return rayon_from_tags(tags) or rayon_from_name(name)
