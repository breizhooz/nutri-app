"""Contrats Pydantic du moteur de cibles nutritionnelles.

Allègement RGPD (2026-10-24) : le serveur n'a plus de donnée corporelle. Les
cibles journalières (kcal + macros) sont calculées sur l'appareil de
l'utilisateur — avec les garde-fous physiologiques (plancher BMR) — ou fixées
par un coach. Le moteur ne fait plus que :
  Étape 2 (step2_user_overrides) : appliquer curseurs et overrides UI ;
  Étape 3 (step3_search_query)   : en déduire des critères de recherche.

Convention de nommage : français sans suffixe `_g` (proteines, glucides, lipides),
cohérente avec le reste du service (cf. app/schemas/calculate.py).
"""

from pydantic import BaseModel, ConfigDict, Field


class DailyTargets(BaseModel):
    """Cibles journalières reçues de l'appareil (ou d'un coach)."""

    calories: float = Field(gt=0)
    proteines: float | None = Field(default=None, ge=0)  # grammes
    lipides: float | None = Field(default=None, ge=0)  # grammes
    glucides: float | None = Field(default=None, ge=0)  # grammes


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
    """Ajustements UI appliqués par-dessus les cibles reçues."""

    manual_calories_override: int | None = None
    manual_proteines_override: int | None = None  # convention française
    tolerances: TargetTolerance = Field(default_factory=TargetTolerance)
    filter_priorities: list[FilterPriority] = Field(default_factory=list)


class FinalTargets(BaseModel):
    """Cibles finales + métadonnées de recherche pour l'Étape 3."""

    calories: float
    proteines: float | None
    lipides: float | None
    glucides: float | None
    tolerances: TargetTolerance
    filter_priorities: list[FilterPriority]
    warnings: list[str] = Field(default_factory=list)


# ── API : contrat de la route d'orchestration ───────────────────────────────
class NutritionTargetsRequest(BaseModel):
    """Entrée de la route : cibles précalculées + préférences non médicales.

    Champ inconnu refusé (422) : aucune donnée corporelle ou médicale n'entre.
    """

    model_config = ConfigDict(extra="forbid")

    diet_type: str = "standard"
    targets: DailyTargets
    adjustment: UserAdjustmentProfile = Field(default_factory=UserAdjustmentProfile)
    excluded_foods: list[str] = Field(default_factory=list)


# ── Étape 3 : critères de recherche (indépendants du moteur de recherche) ───
class MacroTarget(BaseModel):
    """Proximité souhaitée d'une macro par portion : score max à ``target``,
    divisé par deux à ``target ± scale``."""

    field: str  # calories | proteines | lipides | glucides
    target: float
    scale: float


class ScoringPreference(BaseModel):
    """Bonus de score si la recette renseigne le critère ``field``."""

    field: str
    weight: float


class SearchCriteria(BaseModel):
    """Critères de recherche de recettes produits par l'Étape 3.

    Neutres vis-à-vis du moteur : service-recipe les traduit en SQL.
      • ``excluded_tags`` / ``excluded_terms`` / ``required_fields`` : éliminatoires ;
      • ``macro_targets`` / ``preferences`` : scoring souple.
    """

    excluded_tags: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    macro_targets: list[MacroTarget] = Field(default_factory=list)
    preferences: list[ScoringPreference] = Field(default_factory=list)


class NutritionTargetsResponse(BaseModel):
    """Sortie : cibles finales (avec warnings) + critères de recherche."""

    targets: FinalTargets
    search_criteria: SearchCriteria
