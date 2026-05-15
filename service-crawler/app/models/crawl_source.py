import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import CrawlType

class CrawlSource(Base):
    __tablename__ = "crawl_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[CrawlType] = mapped_column(
        SQLEnum(CrawlType, native_enum=False, length=20), nullable=False
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency_hours: Mapped[int] = mapped_column(Integer, default=24)
    execution_hour: Mapped[time] = mapped_column(Time, default=time(3,0))
    last_crawl: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    results: Mapped[list["CrawlResult"]] = relationship(
        back_populates="source", passive_deletes=True
    )