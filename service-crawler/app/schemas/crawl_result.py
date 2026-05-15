import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CrawlStatus, CrawlType


class CrawlResultUpdate(BaseModel):
    titre: str | None = None
    contenu_brut: str | None = None
    images: list[str] | None = None
    video_url: str | None = None


class CrawlResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID | None
    user_id: uuid.UUID | None
    type: CrawlType
    url_origin: str
    title: str
    raw_content: str | None
    images: list[str]
    video_url: str | None
    status: CrawlStatus
    validate_by: uuid.UUID | None
    validate_date: datetime | None
    created_at: datetime