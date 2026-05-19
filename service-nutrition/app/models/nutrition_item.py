import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.models.enums.enums import NutritionSource


class NutritionItem(Base):
    __tablename__ = "nutrition_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    nom_fr: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    nom_en: Mapped[str | None] = mapped_column(String(512), nullable=True)

    nom_sci: Mapped[str | None] = mapped_column(String(512), nullable=True)
    alim_grp_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    alim_ssgrp_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alim_ssssgrp_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    code_confiance: Mapped[str | None] = mapped_column(String(1), nullable=True)

    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    proteines: Mapped[float | None] = mapped_column(Float, nullable=True)
    glucides: Mapped[float | None] = mapped_column(Float, nullable=True)
    lipides: Mapped[float | None] = mapped_column(Float, nullable=True)
    fibres: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[NutritionSource] = mapped_column(
        SQLEnum(NutritionSource, native_enum=False, length=20),
        nullable=False,
        default=NutritionSource.user,
    )

    ciqual_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    # Open Food Facts
    off_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    off_enriched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )