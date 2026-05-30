"""Contrats Pydantic du moteur de cibles nutritionnelles (3 couches découplées).

Convention de nommage : français sans suffixe `_g` (proteines, glucides, lipides),
cohérente avec le reste du service (cf. app/schemas/calculate.py).
"""

from pydantic import BaseModel, Field


# ── Étape 1 : sortie du noyau mathématique ──────────────────────────────────
class BaseTargets(BaseModel):
    """Cibles théoriques pures (physiologie uniquement, aucun profil UI)."""

    calories: float
    proteines: float  # grammes
    lipides: float  # grammes
    glucides: float  # grammes


# ── Étape 2 : entrées de la couche d'ajustement & sécurité ──────────────────
class TargetTolerance(BaseModel):
    """Marges de tolérance pilotées par l'UI (« glissière variété »)."""

    calories_pct: float = 0.10  # ±10 %
    macros_pct: float = 0.15  # ±15 % sur les grammes de macros


class FilterPriority(BaseModel):
    """Priorité d'un critère : filtre strict (MUST) ou scoring souple (SHOULD)."""

    field_name: str  # ex : "cooking_time", "budget", "cooking_level"
    is_strict: bool = False  # True → clause MUST/FILTER | False → scoring SHOULD
    ui_weight: float = 1.0  # multiplicateur de score (0.5 peu important, 2.0 crucial)


class UserAdjustmentProfile(BaseModel):
    """Profil d'ajustement utilisateur appliqué par-dessus les cibles de base."""

    manual_calories_override: int | None = None
    manual_proteines_override: int | None = None  # convention française
    aggressiveness_factor: float = 1.0  # curseur Doux(0.5) / Modéré(1.0) / Intense(1.5)
    tolerances: TargetTolerance = Field(default_factory=TargetTolerance)
    filter_priorities: list[FilterPriority] = Field(default_factory=list)


# ── Étape 2 : sortie sécurisée ──────────────────────────────────────────────
class FinalTargets(BaseModel):
    """Cibles finales sécurisées + métadonnées de recherche pour l'Étape 3."""

    calories: float
    proteines: float
    lipides: float
    glucides: float
    tolerances: TargetTolerance
    filter_priorities: list[FilterPriority]
    warnings: list[str] = Field(default_factory=list)


# ── API : contrat de la route d'orchestration ───────────────────────────────
class NutritionTargetsRequest(BaseModel):
    """Entrée de la route d'orchestration des 3 étapes."""

    goal: str
    diet_type: str = "standard"
    tdee_kcal: float
    bmr_kcal: float
    weight_kg: float
    adjustment: UserAdjustmentProfile = Field(default_factory=UserAdjustmentProfile)
    excluded_foods: list[str] = Field(default_factory=list)
    medical_contraindications: list[str] = Field(default_factory=list)


class NutritionTargetsResponse(BaseModel):
    """Sortie : cibles finales (avec warnings) + requête Elasticsearch construite."""

    targets: FinalTargets
    search_query: dict
