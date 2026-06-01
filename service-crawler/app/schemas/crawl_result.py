import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CrawlStatus, CrawlType


class CrawlResultUpdate(BaseModel):
    title: str | None = None
    raw_content: str | None = None
    images: list[str] | None = None
    video_url: str | None = None


class CrawlResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID | None
    user_id: uuid.UUID
    type: CrawlType
    url_origin: str
    title: str
    raw_content: str | None
    images: list[str]
    video_url: str | None
    published_at: datetime | None
    status: CrawlStatus
    validate_by: uuid.UUID | None
    validate_date: datetime | None
    created_at: datetime

    @classmethod
    def from_link(cls, link: object) -> "CrawlResultResponse":
        r = link.result  # type: ignore[union-attr]
        return cls(
            id=r.id,
            source_id=link.source_id,
            user_id=link.user_id,
            type=r.type,
            url_origin=r.url_origin,
            title=r.title,
            raw_content=r.raw_content,
            images=r.images,
            video_url=r.video_url,
            published_at=r.published_at,
            status=link.status,
            validate_by=link.validate_by,
            validate_date=link.validate_date,
            created_at=r.created_at,
        )


class CrawlResultListParams(BaseModel):
    status: CrawlStatus | None = CrawlStatus.WAITING
    crawl_type: CrawlType | None = None
    source_id: uuid.UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    sort: str = Field(default="desc", pattern="^(asc|desc)$")


class PaginatedCrawlResultResponse(BaseModel):
    items: list[CrawlResultResponse]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def build(
        cls,
        items: list,
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedCrawlResultResponse":
        pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items, total=total, page=page, page_size=page_size, pages=pages
        )
