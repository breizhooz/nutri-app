"""Modèle MedicalCondition — pathologie métabolique, digestive ou autre."""

import logging
import uuid

from sqlalchemy import Boolean, Text, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin
from app.models.enums import MedicalCategory

logger = logging.getLogger(__name__)


class MedicalCondition(Base, SlugMixin, TimestampMixin):
    """Pathologie déclarée — sécurise les suggestions nutritionnelles et sportives."""

    __tablename__ = "medical_conditions"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    category: Mapped[MedicalCategory] = mapped_column(
        SQLEnum(MedicalCategory, native_enum=False, length=20), nullable=False
    )
    condition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
