"""Modèle BodyMeasurementsSnapshot — mensurations corporelles datées."""
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class BodyMeasurementsSnapshot(Base, SlugMixin, TimestampMixin):
    """Instantané de mensurations daté — suivi des circonférences sans dépendre du poids."""

    __tablename__ = "body_measurements_snapshots"

    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    waist_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    hips_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    chest_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    shoulders_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    left_arm_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    right_arm_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    left_thigh_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    right_thigh_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)