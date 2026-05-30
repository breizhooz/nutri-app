"""Étape 3 — Moteur de requête & scoring Elasticsearch.

Construit un query DSL pour l'index **recettes** (distinct de l'index
``nutrition_items`` utilisé par LookupService).

Sépare strictement :
  • Filtres stricts (sécurité/éthique + is_strict)  → ``must_not`` / ``filter`` (éliminent)
  • Scoring souple (is_strict=False + proximité macros) → ``functions`` (réduisent le score)

Consomme ``FinalTargets`` en LECTURE SEULE : ne recalcule jamais calories/macros.
"""

from app.schemas.engine import FilterPriority, FinalTargets

# Champ ES listant les ingrédients normalisés d'une recette.
_INGREDIENTS_FIELD = "ingredients"

# Ingrédients bannis par régime éthique/religieux (filtre strict niveau 0).
_DIET_BANNED_INGREDIENTS: dict[str, list[str]] = {
    "vegan": ["viande", "poisson", "fruits_de_mer", "oeuf", "lait", "miel", "gelatine"],
    "vegetarian": ["viande", "poisson", "fruits_de_mer", "gelatine"],
    "pescatarian": ["viande", "gelatine"],
    "halal": ["porc", "alcool", "gelatine"],
    "kosher": ["porc", "fruits_de_mer"],
    "no_pork": ["porc"],
}


class SearchQueryBuilder:
    """Construit la requête Elasticsearch à partir des cibles finales sécurisées."""

    def build(
        self,
        targets: FinalTargets,
        excluded_foods: list[str],
        diet_type: str,
        medical_contraindications: list[str],
    ) -> dict:
        """Retourne un query DSL Elasticsearch (``function_score``)."""
        must_not = self._build_exclusion_clauses(
            excluded_foods, diet_type, medical_contraindications
        )
        filters = self._build_strict_filters(targets.filter_priorities)
        scoring = self._build_scoring_functions(targets)

        return {
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "must_not": must_not,
                            "filter": filters,
                        }
                    },
                    "functions": scoring,
                    "score_mode": "sum",
                    "boost_mode": "replace",
                }
            }
        }

    # ── Filtres stricts (éliminatoires) ─────────────────────────────────────
    @staticmethod
    def _build_exclusion_clauses(
        excluded_foods: list[str],
        diet_type: str,
        medical_contraindications: list[str],
    ) -> list[dict]:
        """Clauses ``must_not`` : aliments exclus, contre-indications, régime."""
        clauses: list[dict] = []

        if excluded_foods:
            clauses.append({"terms": {_INGREDIENTS_FIELD: list(excluded_foods)}})
        if medical_contraindications:
            clauses.append(
                {"terms": {_INGREDIENTS_FIELD: list(medical_contraindications)}}
            )

        banned = _DIET_BANNED_INGREDIENTS.get(diet_type)
        if banned:
            clauses.append({"terms": {_INGREDIENTS_FIELD: banned}})

        return clauses

    @staticmethod
    def _build_strict_filters(filter_priorities: list[FilterPriority]) -> list[dict]:
        """Clauses ``filter`` pour chaque priorité ``is_strict=True``.

        Le contrat ``FilterPriority`` ne porte pas de valeur cible ; un critère
        strict exige donc au minimum la présence du champ sur la recette.
        """
        return [
            {"exists": {"field": fp.field_name}}
            for fp in filter_priorities
            if fp.is_strict
        ]

    # ── Scoring souple (non éliminatoire) ───────────────────────────────────
    def _build_scoring_functions(self, targets: FinalTargets) -> list[dict]:
        """Fonctions de score : proximité macros + priorités souples pondérées."""
        functions: list[dict] = []

        # Proximité des macros/calories (toujours souple).
        functions.append(
            self._decay_function(
                "calories", targets.calories, targets.tolerances.calories_pct
            )
        )
        for field in ("proteines", "lipides", "glucides"):
            functions.append(
                self._decay_function(
                    field, getattr(targets, field), targets.tolerances.macros_pct
                )
            )

        # Priorités configurables : is_strict=False → scoring uniquement.
        for fp in targets.filter_priorities:
            if not fp.is_strict:
                functions.append(self._weighted_preference(fp))

        return functions

    @staticmethod
    def _decay_function(field: str, target: float, tolerance_pct: float) -> dict:
        """Décroissance gaussienne : score maximal à la cible, réduit hors tolérance.

        Filtrée sur ``exists`` : les recettes sans macro renseignée ne sont pas
        scorées (et n'altèrent pas la requête si le champ est absent du document).
        """
        scale = max(abs(target) * tolerance_pct, 1e-6)
        return {
            "filter": {"exists": {"field": field}},
            "gauss": {field: {"origin": target, "scale": scale, "decay": 0.5}},
            "weight": 1.0,
        }

    @staticmethod
    def _weighted_preference(fp: FilterPriority) -> dict:
        """Bonus de score pondéré par ``ui_weight`` si la recette porte le critère."""
        return {
            "filter": {"exists": {"field": fp.field_name}},
            "weight": fp.ui_weight,
        }
