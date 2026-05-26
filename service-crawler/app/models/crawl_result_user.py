from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import CrawlStatus

if TYPE_CHECKING:
    from app.models.crawl_result import CrawlResult
    from app.models.crawl_source import CrawlSource


class CrawlResultUser(Base):
    __tablename__ = "crawl_result_users"
    __table_args__ = (
        UniqueConstraint("result_id", "user_id", name="uq_crawl_result_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[CrawlStatus] = mapped_column(
        SQLEnum(CrawlStatus, native_enum=False, length=20),
        default=CrawlStatus.WAITING,
        nullable=False,
    )
    validate_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    validate_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    result: Mapped["CrawlResult"] = relationship(back_populates="user_links")
    source: Mapped["CrawlSource | None"] = relationship()
