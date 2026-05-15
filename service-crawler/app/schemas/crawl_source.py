import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict

from app.models.enums import CrawlType

class CrawlSourceCreate(BaseModel):
    type: CrawlType
    url: str
    frequency_hours: int = 24
    execution_hour: time = time(3, 0)

class CrawlSourceUpdate(BaseModel):
    actif: bool | None = None
    frequency_hours: int | None = None
    execution_hour: time | None = None

class CrawlSourceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: CrawlType
    url: str
    actif: bool
    frequency_hours: int
    execution_hour: time
    last_crawl: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
