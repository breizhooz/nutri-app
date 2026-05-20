import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums.enums import MacroErrorStatus


class MacroErrorResponse(BaseModel):
    id: uuid.UUID
    slug: str
    user_id: uuid.UUID
    recipe_id: uuid.UUID | None
    raw_ingredient: str
    suggested_match: str | None
    match_score: float | None
    status: MacroErrorStatus
    resolved_name: str | None
    calories_manual: float | None
    proteines_manual: float | None
    glucides_manual: float | None
    lipides_manual: float | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MacroErrorPatch(BaseModel):
    resolved_name: str
    calories_manual: float | None = None
    proteines_manual: float | None = None
    glucides_manual: float | None = None
    lipides_manual: float | None = None