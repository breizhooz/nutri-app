"""Journal d'effacement RGPD (art. 17) — orchestration cross-service.

Une ligne par couple (requête, service cible). Permet la reprise idempotente sur
échec partiel : le worker Celery rejoue les cibles qui ne sont pas encore
``done``, et le journal reste auditable (exigence RGPD).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ErasureTarget(Base):
    """Cible d'effacement (un microservice) pour une requête de suppression."""

    __tablename__ = "erasure_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Regroupe les cibles d'une même suppression de compte.
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # JSON portable (SQLite tests / JSONB en migration) — liste de comptes (str).
    account_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
