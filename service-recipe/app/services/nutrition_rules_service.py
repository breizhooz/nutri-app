"""Orchestrateur : applique les règles nutritionnelles d'un user à la recherche.

Flux :
  1. Récupère le résumé nutrition de l'utilisateur (service-profile).
  2. Si les règles sont activées et les données suffisantes, appelle le moteur de
     cibles (service-nutrition) pour obtenir les clauses Elasticsearch.
  3. Fusionne ces clauses dans la recherche scopée à l'utilisateur.

Best-effort : à chaque maillon manquant ou en erreur, on retombe proprement sur
une recherche standard (sans règles). Aucun calcul nutritionnel ici.
"""

import logging
import uuid

from app.core.config import settings
from app.core.http_client import NutritionServiceClient
from app.services.profile_client import ProfileClient
from app.services.search_service import search_service

logger = logging.getLogger(__name__)


def _coalesce(override, default):
    """Retourne l'override live s'il est fourni, sinon le défaut persisté."""
    return override if override is not None else default


class NutritionRulesService:
    """Décide et applique la personnalisation nutritionnelle de la recherche."""

    def __init__(
        self,
        profile_client: ProfileClient | None = None,
        nutrition_client: NutritionServiceClient | None = None,
        search=search_service,
    ) -> None:
        self._profile = profile_client or ProfileClient()
        self._nutrition = nutrition_client or NutritionServiceClient()
        self._search = search

    async def search(
        self,
        user_id: str,
        account_id: str,
        apply_rules: bool = True,
        aggressiveness: float | None = None,
        variety_pct: float | None = None,
        override_calories: int | None = None,
        override_proteines: int | None = None,
        **params,
    ) -> dict:
        """Recherche personnalisée si les règles du user sont actives, sinon standard.

        Multicomptes : les recettes sont filtrées par ``account_id`` (compte actif),
        tandis que les règles/cibles nutritionnelles restent résolues par ``user_id``
        (dossier via service-profile).
        """
        if not apply_rules:
            return await self._search.search_recipes(account_id=account_id, **params)

        engine_inputs = await self._resolve_engine_inputs(user_id)
        if engine_inputs is None:
            return await self._search.search_recipes(account_id=account_id, **params)

        adjustment = self._build_adjustment(
            engine_inputs.pop("_prefs"),
            aggressiveness,
            variety_pct,
            override_calories,
            override_proteines,
        )
        result = await self._nutrition.compute_targets(
            **engine_inputs, adjustment=adjustment
        )
        if result is None:
            return await self._search.search_recipes(account_id=account_id, **params)

        clauses = self._extract_clauses(result.search_query)
        response = await self._search.search_recipes(
            account_id=account_id,
            **params,
            extra_must_not=clauses["must_not"],
            extra_filter=clauses["filter"],
            scoring_functions=(
                clauses["functions"] if settings.APPLY_NUTRITION_SCORING else None
            ),
        )
        # Cibles + warnings remontés pour affichage UI.
        response["nutrition_targets"] = result.targets
        return response

    async def _resolve_engine_inputs(self, user_id: str) -> dict | None:
        """Construit les entrées du moteur depuis le résumé, ou None si inapplicable."""
        try:
            summary = await self._profile.get_nutrition_summary(uuid.UUID(user_id))
        except ValueError:
            return None
        if summary is None:
            return None

        profile = summary.profile
        if profile is None or not profile.nutrition_rules_enabled:
            return None

        calc = summary.calculation
        prefs = summary.nutrition_preferences
        if calc is None or prefs is None or profile.weight_kg is None:
            return None

        excluded_foods = list(prefs.excluded_foods) + [
            e.food_name for e in summary.excluded_foods
        ]
        contraindications = [a.allergen for a in summary.allergies]

        return {
            "goal": prefs.main_goal,
            "diet_type": prefs.diet_type,
            "tdee_kcal": calc.tdee_kcal,
            "bmr_kcal": calc.bmr_kcal,
            "weight_kg": profile.weight_kg,
            "excluded_foods": excluded_foods,
            "medical_contraindications": contraindications,
            # Préférences (défauts d'ajustement persistés) — retiré avant l'appel moteur.
            "_prefs": prefs,
        }

    @staticmethod
    def _build_adjustment(
        prefs,
        aggressiveness: float | None,
        variety_pct: float | None,
        override_calories: int | None,
        override_proteines: int | None,
    ) -> dict | None:
        """Assemble le profil d'ajustement, ou None si aucun réglage.

        Les curseurs live (query params) ont priorité ; à défaut, on utilise les
        réglages par défaut persistés sur le profil (``rules_*``).
        La glissière variété pilote la tolérance calories ; la tolérance macros
        conserve l'écart de +5 pts des valeurs par défaut (0.10 → 0.15).
        """
        agg = _coalesce(aggressiveness, getattr(prefs, "rules_aggressiveness", None))
        var = _coalesce(variety_pct, getattr(prefs, "rules_variety_pct", None))
        oc = _coalesce(
            override_calories, getattr(prefs, "rules_override_calories", None)
        )
        op = _coalesce(
            override_proteines, getattr(prefs, "rules_override_proteines", None)
        )

        adjustment: dict = {}
        if agg is not None:
            adjustment["aggressiveness_factor"] = agg
        if oc is not None:
            adjustment["manual_calories_override"] = oc
        if op is not None:
            adjustment["manual_proteines_override"] = op
        if var is not None:
            adjustment["tolerances"] = {
                "calories_pct": var,
                "macros_pct": round(var + 0.05, 4),
            }
        return adjustment or None

    @staticmethod
    def _extract_clauses(search_query: dict) -> dict:
        """Extrait must_not / filter / functions de la requête du moteur (lecture seule)."""
        function_score = search_query.get("query", {}).get("function_score", {})
        bool_query = function_score.get("query", {}).get("bool", {})
        return {
            "must_not": bool_query.get("must_not", []),
            "filter": bool_query.get("filter", []),
            "functions": function_score.get("functions", []),
        }


nutrition_rules_service = NutritionRulesService()
