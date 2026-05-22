"""Modèle BodyCompositionSnapshot — mesure ponctuelle de composition corporelle."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin

logger = logging.getLogger(__name__)


class BodyCompositionSnapshot(Base, SlugMixin, TimestampMixin):
    """Instantané de composition corporelle daté — s'accumule pour le suivi temporel."""

    __tablename__ = "body_composition_snapshots"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    body_fat_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True
    )
    lean_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    bone_mass_kg: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    water_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True
    )
