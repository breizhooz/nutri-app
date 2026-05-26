from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import CrawlType

if TYPE_CHECKING:
    from app.models.crawl_result_user import CrawlResultUser


class CrawlResult(Base):
    __tablename__ = "crawl_results"
    __table_args__ = (
        UniqueConstraint("url_origin", name="uq_crawl_results_url_origin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[CrawlType] = mapped_column(
        SQLEnum(CrawlType, native_enum=False, length=20), nullable=False
    )
    url_origin: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=[], server_default="{}"
    )
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user_links: Mapped[list["CrawlResultUser"]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
