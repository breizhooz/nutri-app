"""SQLAlchemy ORM model for the users table."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def default_user_right() -> dict[str, Any]:
    """Default RBAC rights granted to a freshly created user (nothing allowed)."""
    return {"crawl": {"instagram": False, "web": False}}


class User(Base):
    """Represents an authenticated user account.

    Supports local email/password authentication and OAuth2 social login.
    The hashed_password field is nullable to allow OAuth-only accounts.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Type JSON générique (portable SQLite/PG) ; la colonne réelle est JSONB
    # côté Postgres via la migration. Défaut côté Python ; le server_default
    # JSONB n'est posé que dans la migration (backfill des lignes existantes).
    user_right: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=default_user_right,
        nullable=False,
    )
    totp_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    two_factor_method: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
