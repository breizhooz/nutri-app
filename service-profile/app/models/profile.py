"""Modèle Profile — noyau central, données anthropométriques de base."""

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Numeric, false
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import SlugMixin, TimestampMixin, UpdatedAtMixin
from app.models.enums import BiologicalSex

logger = logging.getLogger(__name__)


class Profile(Base, SlugMixin, TimestampMixin, UpdatedAtMixin):
    """Profil principal d'un utilisateur.

    Relation 1-to-1 logique avec service-user via user_id.
    Aucune FK physique inter-services — cohérence assurée par les appels HTTP.
    """

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    biological_sex: Mapped[BiologicalSex | None] = mapped_column(
        SQLEnum(BiologicalSex, native_enum=False, length=20), nullable=True
    )
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    nutrition_rules_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
