"""Mixins de colonnes réutilisables pour les modèles SQLAlchemy 2.0."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class SlugMixin:
    """Fournit id (UUID PK) et slug (identifiant URL unique, généré côté Python)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)


class TimestampMixin:
    """Fournit created_at horodaté côté serveur à l'insertion."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UpdatedAtMixin:
    """Fournit updated_at horodaté côté serveur à l'insertion, mis à jour manuellement."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )