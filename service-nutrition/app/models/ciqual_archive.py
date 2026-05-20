import uuid
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base

class CiqualArchive(Base):
    __tablename__ = "ciqual_archives"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(100), nullable=False)   # "2025_11_03.7z"
    version: Mapped[str] = mapped_column(String(20), nullable=False)     # "2025_11_03"
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )