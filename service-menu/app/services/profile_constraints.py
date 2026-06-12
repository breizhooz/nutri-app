"""Contraintes de génération issues du profil utilisateur (service-profile).

Traduit le résumé nutritionnel inter-service (GET /profiles/{user_id}/
nutrition-summary) en contraintes exploitables par le randomizer :

  • ``allergen_tags``        — allergies déclarées → tags ``enums.allergen.*``
  • ``forbidden_tags``       — régime (diet_type) → tags ``enums.type_of_ingredient.*``
  • ``excluded_food_terms``  — aliments exclus (et allergènes, en défense en
                               profondeur) → match sur le NOM des ingrédients
  • ``target_calories``      — cible énergétique calculée, utilisée comme défaut

Le mapping régime est aligné sur la sémantique du moteur de service-nutrition
(``step3_search_query._DIET_BANNED_INGREDIENTS``) mais appliqué ici sur les
tags réels des ingrédients, seules données fiables du payload recette. Le porc
n'ayant pas de tag dédié, halal/kosher/no_pork passent par une exclusion par
noms d'ingrédients (best-effort documenté).

NB : ``nutrition_preferences.medical_contraindications`` est un champ de prose
libre — il n'est volontairement pas interprété ici.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property

from app.models.enums import Allergen


def _normalize(text: str) -> str:
    """Minuscules, sans accents, espaces compactés — base de tout matching."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.strip().lower())


# ── Allergies : libellé libre (fr/en) → tag Allergen ───────────────────────
# Clés au singulier normalisé ; le lookup tente aussi le singulier naïf
# (suppression du « s » final). Un libellé non mappé n'est jamais perdu : il
# bascule en exclusion par nom d'ingrédient.
_ALLERGEN_SYNONYMS: dict[str, Allergen] = {
    "gluten": Allergen.GLUTEN,
    "ble": Allergen.GLUTEN,
    "wheat": Allergen.GLUTEN,
    "crustace": Allergen.CRUSTACEANS,
    "crustacean": Allergen.CRUSTACEANS,
    "crevette": Allergen.CRUSTACEANS,
    "oeuf": Allergen.EGGS,
    "egg": Allergen.EGGS,
    "poisson": Allergen.FISH,
    "fish": Allergen.FISH,
    "arachide": Allergen.PEANUTS,
    "cacahuete": Allergen.PEANUTS,
    "peanut": Allergen.PEANUTS,
    "soja": Allergen.SOY,
    "soy": Allergen.SOY,
    "soya": Allergen.SOY,
    "lait": Allergen.MILK,
    "milk": Allergen.MILK,
    "lactose": Allergen.MILK,
    "noix": Allergen.NUTS,
    "fruit a coque": Allergen.NUTS,
    "fruits a coque": Allergen.NUTS,
    "nut": Allergen.NUTS,
    "amande": Allergen.NUTS,
    "noisette": Allergen.NUTS,
    "celeri": Allergen.CELERY,
    "celery": Allergen.CELERY,
    "moutarde": Allergen.MUSTARD,
    "mustard": Allergen.MUSTARD,
    "sesame": Allergen.SESAME,
    "sulfite": Allergen.SULPHITES,
    "sulphite": Allergen.SULPHITES,
    "lupin": Allergen.LUPIN,
    "mollusque": Allergen.MOLLUSCS,
    "mollusc": Allergen.MOLLUSCS,
    "mais": Allergen.CORN,
    "corn": Allergen.CORN,
    "ail": Allergen.GARLIC,
    "garlic": Allergen.GARLIC,
    "oignon": Allergen.ONION,
    "onion": Allergen.ONION,
}

# ── Régime : groupes de tags TypeOfIngredient (contrat inter-service) ───────
_MEAT_TAGS = {
    "enums.type_of_ingredient.meat",
    "enums.type_of_ingredient.white_meat",
    "enums.type_of_ingredient.red_meat",
    "enums.type_of_ingredient.processed_meat",
}
_FISH_TAGS = {
    "enums.type_of_ingredient.fish",
    "enums.type_of_ingredient.white_fish",
    "enums.type_of_ingredient.fatty_fish",
    "enums.type_of_ingredient.smoked_fish",
}
_SEAFOOD_TAGS = {
    "enums.type_of_ingredient.seafood",
    "enums.type_of_ingredient.crustacean",
    "enums.type_of_ingredient.mollusc",
}
_DAIRY_TAGS = {
    "enums.type_of_ingredient.dairy",
    "enums.type_of_ingredient.milk",
    "enums.type_of_ingredient.cheese",
    "enums.type_of_ingredient.yogurt",
    "enums.type_of_ingredient.butter",
    "enums.type_of_ingredient.cream",
}
_EGG_TAGS = {"enums.type_of_ingredient.egg"}
_HONEY_TAGS = {"enums.type_of_ingredient.honey"}
_ALCOHOL_TAGS = {
    "enums.type_of_ingredient.alcohol",
    "enums.type_of_ingredient.wine",
    "enums.type_of_ingredient.beer",
    "enums.type_of_ingredient.spirit",
}

# Pas de tag « porc » dans TypeOfIngredient → exclusion par noms (best-effort).
_PORK_TERMS = {"porc", "pork", "jambon", "lard", "lardon", "bacon", "chorizo",
               "saucisson", "pancetta"}
_GELATIN_TERMS = {"gelatine", "gelatin"}

# diet_type (valeurs de l'enum DietType de service-profile) → contraintes.
# keto/omnivore/other : profils macro ou sans interdit strict → aucun filtre dur.
_DIET_FORBIDDEN_TAGS: dict[str, set[str]] = {
    "vegan": _MEAT_TAGS | _FISH_TAGS | _SEAFOOD_TAGS | _DAIRY_TAGS | _EGG_TAGS
    | _HONEY_TAGS,
    "vegetarian": _MEAT_TAGS | _FISH_TAGS | _SEAFOOD_TAGS,
    "pescatarian": _MEAT_TAGS,
    "halal": _ALCOHOL_TAGS,
    "kosher": _SEAFOOD_TAGS,
}
_DIET_FORBIDDEN_TERMS: dict[str, set[str]] = {
    "vegan": _GELATIN_TERMS,
    "vegetarian": _GELATIN_TERMS,
    "pescatarian": _GELATIN_TERMS,
    "halal": _PORK_TERMS | _GELATIN_TERMS,
    "kosher": _PORK_TERMS,
    "no_pork": _PORK_TERMS,
}


@dataclass(frozen=True)
class ProfileConstraints:
    """Contraintes dures dérivées du profil, consommées par le randomizer."""

    allergen_tags: frozenset[str] = frozenset()
    forbidden_tags: frozenset[str] = frozenset()
    excluded_food_terms: frozenset[str] = frozenset()
    target_calories: int | None = None

    @property
    def excluded_tags(self) -> frozenset[str]:
        """Tous les tags éliminatoires (allergènes + régime)."""
        return self.allergen_tags | self.forbidden_tags

    @cached_property
    def _terms_pattern(self) -> re.Pattern | None:
        if not self.excluded_food_terms:
            return None
        alternation = "|".join(
            re.escape(term) + "s?" for term in sorted(self.excluded_food_terms)
        )
        return re.compile(rf"\b(?:{alternation})\b")

    def matches_excluded_name(self, ingredient_name: str) -> bool:
        """Vrai si le nom d'ingrédient contient un aliment exclu.

        Match en mot entier sur nom normalisé (« lait » exclut « Lait entier »
        mais pas « laitue »), tolérant au pluriel naïf.
        """
        if self._terms_pattern is None or not ingredient_name:
            return False
        return bool(self._terms_pattern.search(_normalize(ingredient_name)))


def _map_allergen(label: str) -> Allergen | None:
    term = _normalize(label)
    found = _ALLERGEN_SYNONYMS.get(term)
    if found is None and term.endswith("s"):
        found = _ALLERGEN_SYNONYMS.get(term[:-1])
    return found


def build_constraints(summary: dict | None) -> ProfileConstraints:
    """Construit les contraintes depuis le résumé nutritionnel (ou rien).

    ``summary`` est le JSON brut de service-profile ; None (pas de profil ou
    intégration désactivée) produit des contraintes vides.
    """
    if not summary:
        return ProfileConstraints()

    allergen_tags: set[str] = set()
    food_terms: set[str] = set()

    # Allergies : tag si mappable + toujours le nom (défense en profondeur).
    for allergy in summary.get("allergies") or []:
        label = allergy.get("allergen") or ""
        if not label.strip():
            continue
        mapped = _map_allergen(label)
        if mapped is not None:
            allergen_tags.add(mapped.value)
        food_terms.add(_normalize(label))

    # Aliments exclus : modèle dédié + liste libre des préférences.
    for excluded in summary.get("excluded_foods") or []:
        name = excluded.get("food_name") or ""
        if name.strip():
            food_terms.add(_normalize(name))

    prefs = summary.get("nutrition_preferences") or {}
    for name in prefs.get("excluded_foods") or []:
        if name and name.strip():
            food_terms.add(_normalize(name))

    # Régime alimentaire → tags interdits + termes best-effort (porc, gélatine).
    forbidden_tags: set[str] = set()
    diet_type = prefs.get("diet_type")
    if diet_type:
        forbidden_tags |= _DIET_FORBIDDEN_TAGS.get(diet_type, set())
        food_terms |= _DIET_FORBIDDEN_TERMS.get(diet_type, set())

    target_calories = (summary.get("calculation") or {}).get("target_calories_kcal")

    return ProfileConstraints(
        allergen_tags=frozenset(allergen_tags),
        forbidden_tags=frozenset(forbidden_tags),
        excluded_food_terms=frozenset(food_terms),
        target_calories=target_calories,
    )
