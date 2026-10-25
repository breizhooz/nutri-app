"""Schéma du résumé nutritionnel récupéré auprès de service-profile.

Miroir tolérant de ``GET /internal/accounts/{account_id}/nutrition-summary`` :
énumérations typées en ``str``, ``extra="ignore"`` pour rester découplé des
évolutions côté profile. Aucune donnée corporelle ni médicale : les cibles
(kcal + macros) sont calculées sur l'appareil de l'utilisateur ou fixées par un
coach.
"""

import uuid

from pydantic import BaseModel, ConfigDict


class _Loose(BaseModel):
    """Base permissive : ignore les champs inconnus de service-profile."""

    model_config = ConfigDict(extra="ignore")


class TargetsSummary(_Loose):
    """Cibles journalières (convention française du moteur de cibles)."""

    calories: int
    proteines: int | None = None
    glucides: int | None = None
    lipides: int | None = None


class RulesSummary(_Loose):
    """Activation et curseurs persistés de la recherche personnalisée."""

    enabled: bool = False
    variety_pct: float = 0.10
    override_calories: int | None = None
    override_proteines: int | None = None


class NutritionSummary(_Loose):
    """Vue agrégée du profil nutritionnel d'un compte."""

    account_id: uuid.UUID
    main_goal: str
    diet_type: str
    excluded_foods: list[str] = []
    targets: TargetsSummary | None = None
    rules: RulesSummary = RulesSummary()
