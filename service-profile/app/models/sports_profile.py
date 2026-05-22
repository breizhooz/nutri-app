"""Modèle SportsProfile — profil sportif 1-to-1 avec Profile."""

import logging
import uuid

from sqlalchemy import JSON, SmallInteger
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, UpdatedAtMixin
from app.models.enums import PracticeLevel

logger = logging.getLogger(__name__)


class SportsProfile(Base, SlugMixin, UpdatedAtMixin):
    """Profil sportif de l'utilisateur — calibre la dépense énergétique et les substrats."""

    __tablename__ = "sports_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    sports: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    practice_level: Mapped[PracticeLevel] = mapped_column(
        SQLEnum(PracticeLevel, native_enum=False, length=15), nullable=False
    )
    sessions_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    avg_session_duration_min: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    avg_intensity_rpe: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    resting_heart_rate_bpm: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
