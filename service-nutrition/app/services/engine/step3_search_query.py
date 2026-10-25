"""Étape 3 — Critères de recherche & scoring des recettes.

Produit des ``SearchCriteria`` neutres (aucun DSL de moteur de recherche) que
service-recipe traduit en SQL (PostgreSQL plein texte).

Sépare strictement :
  • Filtres stricts (sécurité/éthique + is_strict) → ``excluded_*`` / ``required_fields`` (éliminent)
  • Scoring souple (is_strict=False + proximité macros) → ``macro_targets`` / ``preferences``

Consomme ``FinalTargets`` en LECTURE SEULE : ne recalcule jamais calories/macros.
"""

from app.schemas.engine import (
    FilterPriority,
    FinalTargets,
    MacroTarget,
    ScoringPreference,
    SearchCriteria,
)

# ── Régime : tags TypeOfIngredient interdits (contrat inter-service) ────────
# Aligné sur service-menu (app/services/profile_constraints.py).
_MEAT_TAGS = [
    "enums.type_of_ingredient.meat",
    "enums.type_of_ingredient.white_meat",
    "enums.type_of_ingredient.red_meat",
    "enums.type_of_ingredient.processed_meat",
]
_FISH_TAGS = [
    "enums.type_of_ingredient.fish",
    "enums.type_of_ingredient.white_fish",
    "enums.type_of_ingredient.fatty_fish",
    "enums.type_of_ingredient.smoked_fish",
]
_SEAFOOD_TAGS = [
    "enums.type_of_ingredient.seafood",
    "enums.type_of_ingredient.crustacean",
    "enums.type_of_ingredient.mollusc",
]
_DAIRY_TAGS = [
    "enums.type_of_ingredient.dairy",
    "enums.type_of_ingredient.milk",
    "enums.type_of_ingredient.cheese",
    "enums.type_of_ingredient.yogurt",
    "enums.type_of_ingredient.butter",
    "enums.type_of_ingredient.cream",
]
_EGG_TAGS = ["enums.type_of_ingredient.egg"]
_HONEY_TAGS = ["enums.type_of_ingredient.honey"]
_ALCOHOL_TAGS = [
    "enums.type_of_ingredient.alcohol",
    "enums.type_of_ingredient.wine",
    "enums.type_of_ingredient.beer",
    "enums.type_of_ingredient.spirit",
]

# Pas de tag « porc » ni « gélatine » → exclusion par noms d'ingrédient (best-effort).
_PORK_TERMS = [
    "porc",
    "pork",
    "jambon",
    "lard",
    "lardon",
    "bacon",
    "chorizo",
    "saucisson",
    "pancetta",
]
_GELATIN_TERMS = ["gelatine", "gelatin"]

_DIET_BANNED_TAGS: dict[str, list[str]] = {
    "vegan": _MEAT_TAGS
    + _FISH_TAGS
    + _SEAFOOD_TAGS
    + _DAIRY_TAGS
    + _EGG_TAGS
    + _HONEY_TAGS,
    "vegetarian": _MEAT_TAGS + _FISH_TAGS + _SEAFOOD_TAGS,
    "pescatarian": _MEAT_TAGS,
    "halal": _ALCOHOL_TAGS,
    "kosher": _SEAFOOD_TAGS,
}
_DIET_BANNED_TERMS: dict[str, list[str]] = {
    "vegan": _GELATIN_TERMS,
    "vegetarian": _GELATIN_TERMS,
    "pescatarian": _GELATIN_TERMS,
    "halal": _PORK_TERMS + _GELATIN_TERMS,
    "kosher": _PORK_TERMS,
    "no_pork": _PORK_TERMS,
}

_MACRO_FIELDS = ("calories", "proteines", "lipides", "glucides")


def _dedupe(values: list[str]) -> list[str]:
    """Supprime vides et doublons en conservant l'ordre."""
    seen: dict[str, None] = {}
    for value in values:
        cleaned = value.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


class SearchQueryBuilder:
    """Construit les critères de recherche à partir des cibles finales sécurisées."""

    def build(
        self,
        targets: FinalTargets,
        excluded_foods: list[str],
        diet_type: str,
    ) -> SearchCriteria:
        return SearchCriteria(
            excluded_tags=_dedupe(_DIET_BANNED_TAGS.get(diet_type, [])),
            excluded_terms=_dedupe(
                list(excluded_foods) + _DIET_BANNED_TERMS.get(diet_type, [])
            ),
            required_fields=[
                fp.field_name for fp in targets.filter_priorities if fp.is_strict
            ],
            macro_targets=self._build_macro_targets(targets),
            preferences=self._build_preferences(targets.filter_priorities),
        )

    @staticmethod
    def _build_macro_targets(targets: FinalTargets) -> list[MacroTarget]:
        """Proximité calories (tolérance calories) puis macros (tolérance macros) ;
        une macro non fournie par l'appareil n'est pas scorée."""
        result = []
        for field in _MACRO_FIELDS:
            tolerance = (
                targets.tolerances.calories_pct
                if field == "calories"
                else targets.tolerances.macros_pct
            )
            target = getattr(targets, field)
            if target is None:
                continue
            result.append(
                MacroTarget(
                    field=field,
                    target=target,
                    scale=max(abs(target) * tolerance, 1e-6),
                )
            )
        return result

    @staticmethod
    def _build_preferences(
        filter_priorities: list[FilterPriority],
    ) -> list[ScoringPreference]:
        """Priorités configurables : is_strict=False → scoring uniquement."""
        return [
            ScoringPreference(field=fp.field_name, weight=fp.ui_weight)
            for fp in filter_priorities
            if not fp.is_strict
        ]
