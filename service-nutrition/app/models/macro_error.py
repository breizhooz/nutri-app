import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.enums.enums import MacroErrorStatus


class MacroError(Base):
    __tablename__ = "macro_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(300), unique=True, nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    raw_ingredient: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_match: Mapped[str | None] = mapped_column(String(300), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[MacroErrorStatus] = mapped_column(
        SQLEnum(MacroErrorStatus, native_enum=False, length=20),
        default=MacroErrorStatus.PENDING,
        nullable=False,
    )
    resolved_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    calories_manual: Mapped[float | None] = mapped_column(Float, nullable=True)
    proteines_manual: Mapped[float | None] = mapped_column(Float, nullable=True)
    glucides_manual: Mapped[float | None] = mapped_column(Float, nullable=True)
    lipides_manual: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )