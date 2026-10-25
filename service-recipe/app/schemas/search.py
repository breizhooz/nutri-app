"""Critères de recherche produits par le moteur de cibles (service-nutrition).

Miroir du contrat ``SearchCriteria`` de service-nutrition
(``app/schemas/engine.py``) : neutre vis-à-vis du moteur de recherche,
traduit en SQL par ``RecipeSearchService``.
"""

from pydantic import BaseModel, Field


class MacroTarget(BaseModel):
    field: str
    target: float
    scale: float


class ScoringPreference(BaseModel):
    field: str
    weight: float


class SearchCriteria(BaseModel):
    excluded_tags: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    macro_targets: list[MacroTarget] = Field(default_factory=list)
    preferences: list[ScoringPreference] = Field(default_factory=list)
