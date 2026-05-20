from pydantic import BaseModel


class IngredientInput(BaseModel):
    raw_text: str


class MacroValues(BaseModel):
    calories: float
    proteines: float
    glucides: float
    lipides: float


class ResolvedIngredient(BaseModel):
    raw_text: str
    matched_slug: str
    grammes: float
    macros: MacroValues


class ErrorIngredient(BaseModel):
    raw_text: str
    slug: str
    suggested: str | None


class CalculateRequest(BaseModel):
    recipe_slug: str
    servings: int = 1
    user_id: str
    ingredients: list[IngredientInput]


class CalculateResponse(BaseModel):
    recipe_slug: str
    servings: int
    total: MacroValues
    per_serving: MacroValues
    resolved: list[ResolvedIngredient]
    errors: list[ErrorIngredient]


class LookupResponse(BaseModel):
    slug: str
    nom_fr: str
    nom_en: str | None
    calories: float
    proteines: float
    glucides: float
    lipides: float
    fibres: float | None
    score: float | None = None


class AdminReindexRequest(BaseModel):
    source: str


class AdminReindexResponse(BaseModel):
    job_id: str
    status: str
    source: str


class UserStatsResponse(BaseModel):
    user_slug: str
    period: str
    recipes_analysed: int
    macro_errors_pending: int
    macro_errors_resolved: int
    avg_daily: MacroValues