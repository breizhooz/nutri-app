"""Modèle PerformanceMetric — métriques de performance datées."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class PerformanceMetric(Base, SlugMixin, TimestampMixin):
    """Instantané de performance sportive — VO2Max, VMA, FTP, charges maximales."""

    __tablename__ = "performance_metrics"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    vo2max: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    vma_kmh: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    ftp_watts: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    one_rm_squat_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )
    one_rm_bench_press_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )
    one_rm_deadlift_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )
    one_rm_overhead_press_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 1), nullable=True
    )
