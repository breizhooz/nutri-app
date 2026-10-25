"""Orchestrateur : applique les règles nutritionnelles du compte à la recherche.

Flux :
  1. Récupère le résumé nutrition du compte actif (service-profile).
  2. Si les règles sont activées et que le compte a des cibles (calculées sur
     l'appareil ou fixées par un coach), appelle le moteur (service-nutrition)
     pour obtenir les critères de recherche.
  3. Applique ces critères à la recherche scopée au compte actif.

Best-effort : à chaque maillon manquant ou en erreur, on retombe proprement sur
une recherche standard (sans règles). Aucun calcul nutritionnel ici.
"""

import logging
import uuid

from app.core.config import settings
from app.core.http_client import NutritionServiceClient
from app.services.profile_client import ProfileClient
from app.services.search_service import RecipeSearchService

logger = logging.getLogger(__name__)


def _coalesce(override, default):
    """Retourne l'override live s'il est fourni, sinon le défaut persisté."""
    return override if override is not None else default


class NutritionRulesService:
    """Décide et applique la personnalisation nutritionnelle de la recherche."""

    def __init__(
        self,
        search: RecipeSearchService,
        profile_client: ProfileClient | None = None,
        nutrition_client: NutritionServiceClient | None = None,
    ) -> None:
        self._profile = profile_client or ProfileClient()
        self._nutrition = nutrition_client or NutritionServiceClient()
        self._search = search

    async def search(
        self,
        account_id: str,
        apply_rules: bool = True,
        variety_pct: float | None = None,
        override_calories: int | None = None,
        override_proteines: int | None = None,
        **params,
    ) -> dict:
        """Recherche personnalisée si le compte actif a des règles et des cibles,
        sinon standard.

        Multicomptes : recettes et profil sont tous deux bornés par ``account_id``.
        Les cibles (kcal + macros) sont calculées sur l'appareil de l'utilisateur
        (ou fixées par un coach) : le serveur n'a pas de donnée corporelle.
        """
        if not apply_rules:
            return await self._search.search_recipes(account_id=account_id, **params)

        engine_inputs = await self._resolve_engine_inputs(account_id)
        if engine_inputs is None:
            return await self._search.search_recipes(account_id=account_id, **params)

        adjustment = self._build_adjustment(
            engine_inputs.pop("_rules"),
            variety_pct,
            override_calories,
            override_proteines,
        )
        result = await self._nutrition.compute_targets(
            **engine_inputs, adjustment=adjustment
        )
        if result is None:
            return await self._search.search_recipes(account_id=account_id, **params)

        response = await self._search.search_recipes(
            account_id=account_id,
            **params,
            criteria=result.search_criteria,
            apply_scoring=settings.APPLY_NUTRITION_SCORING,
        )
        # Cibles + warnings remontés pour affichage UI.
        response["nutrition_targets"] = result.targets
        return response

    async def _resolve_engine_inputs(self, account_id: str) -> dict | None:
        """Entrées du moteur depuis le résumé du compte, ou None si inapplicable
        (pas de profil, règles désactivées, ou pas encore de cibles)."""
        try:
            summary = await self._profile.get_nutrition_summary(uuid.UUID(account_id))
        except ValueError:
            return None
        if summary is None or not summary.rules.enabled or summary.targets is None:
            return None

        targets = summary.targets
        return {
            "diet_type": summary.diet_type,
            "targets": {
                "calories": targets.calories,
                "proteines": targets.proteines,
                "glucides": targets.glucides,
                "lipides": targets.lipides,
            },
            "excluded_foods": list(summary.excluded_foods),
            # Réglages persistés (défauts des curseurs) — retiré avant l'appel moteur.
            "_rules": summary.rules,
        }

    @staticmethod
    def _build_adjustment(
        rules,
        variety_pct: float | None,
        override_calories: int | None,
        override_proteines: int | None,
    ) -> dict | None:
        """Assemble le profil d'ajustement, ou None si aucun réglage.

        Les curseurs live (query params) ont priorité ; à défaut, on utilise les
        réglages par défaut persistés sur le profil (``rules``).
        La glissière variété pilote la tolérance calories ; la tolérance macros
        conserve l'écart de +5 pts des valeurs par défaut (0.10 → 0.15).
        """
        var = _coalesce(variety_pct, getattr(rules, "variety_pct", None))
        oc = _coalesce(override_calories, getattr(rules, "override_calories", None))
        op = _coalesce(override_proteines, getattr(rules, "override_proteines", None))

        adjustment: dict = {}
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
