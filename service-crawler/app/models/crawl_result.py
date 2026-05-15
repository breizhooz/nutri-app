import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import CrawlStatus, CrawlType


class CrawlResult(Base):
    __tablename__ = "crawl_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[CrawlType] = mapped_column(
        SQLEnum(CrawlType, native_enum=False, length=20), nullable=False
    )
    url_origin: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[str]] = mapped_column(ARRAY(String), default=[], server_default="{}")
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[CrawlStatus] = mapped_column(
        SQLEnum(CrawlStatus, native_enum=False, length=20),
        default=CrawlStatus.WAITING,
        nullable=False,
    )
    validate_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    validate_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped["CrawlSource | None"] = relationship(back_populates="results")