"""SQLAlchemy ORM models for the multi-account access layer.

This is the CRM backbone described in ``docs/roles/``: an identity (the existing
``users`` row) can hold a ``Membership`` on one or more ``Account`` (data
perimeters), each membership carrying a named ``Role`` whose permissions are a
set of ``Scope``. ``MembershipScopeOverride`` is the fine-grained escape hatch.

Design notes (mirroring the conventions already used by ``app/models/user.py``):

* Primary keys default to ``uuid.uuid4`` on the Python side so the models work
  unchanged on SQLite (unit tests) and Postgres (runtime). The DB-level
  ``gen_random_uuid()`` default is only set in the Alembic migration.
* ``users.default_account_id`` is declared as a plain column (no ORM-level
  ForeignKey) to avoid a mutual ``users <-> accounts`` FK cycle that SQLite's
  ``create_all`` cannot resolve. The real FK constraint is added in the
  migration (Postgres), the same way ``user_right`` is ``JSON`` in the ORM but
  ``JSONB`` in the migration.
* The ``identity_id`` columns are conceptual identity references; physically
  they point at the kept ``users`` table (no ``users -> identities`` rename in
  this increment).
"""

import uuid
from datetime import datetime
from typing import Optional

from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    """A data perimeter (the nutritional dossier) shared via memberships."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="personal", nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list["Membership"]] = relationship(back_populates="account")

    __table_args__ = (
        CheckConstraint("type IN ('personal','managed')", name="ck_account_type"),
    )


class Role(Base):
    """Catalogue of named roles (seed/reference data)."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)


class Scope(Base):
    """Catalogue of fine-grained permissions (seed/reference data)."""

    __tablename__ = "scopes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class RoleScope(Base):
    """Maps a role to the scopes it grants (seed/reference data)."""

    __tablename__ = "role_scopes"

    role_code: Mapped[str] = mapped_column(
        ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True
    )
    scope_code: Mapped[str] = mapped_column(
        ForeignKey("scopes.code", ondelete="CASCADE"), primary_key=True
    )


class Membership(Base):
    """Pivot identity <-> account carrying a role. The heart of the system.

    Permissions belong to this link, never to the identity nor the account
    alone. Unique ``(identity_id, account_id)``: one role per account per
    identity.
    """

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped["Account"] = relationship(back_populates="memberships")
    overrides: Mapped[list["MembershipScopeOverride"]] = relationship(
        back_populates="membership", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("identity_id", "account_id", name="uq_membership"),
        CheckConstraint(
            "status IN ('active','suspended','revoked')", name="ck_membership_status"
        ),
    )


class MembershipScopeOverride(Base):
    """Per-membership scope adjustment (grant adds, deny removes; deny wins)."""

    __tablename__ = "membership_scope_overrides"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scope_code: Mapped[str] = mapped_column(
        ForeignKey("scopes.code", ondelete="CASCADE"), primary_key=True
    )
    effect: Mapped[str] = mapped_column(String(8), nullable=False)

    membership: Mapped["Membership"] = relationship(back_populates="overrides")

    __table_args__ = (
        CheckConstraint("effect IN ('grant','deny')", name="ck_override_effect"),
    )


class Invitation(Base):
    """Pending share of an account to an email, with a role and an expiry token.

    Découple le partage de l'existence préalable du login : l'invité peut ne pas
    encore avoir d'identité. À l'acceptation (si l'email correspond à une
    identité), un :class:`Membership` est créé.
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), nullable=False)
    # 'collaborator' : l'invité rejoint le compte de l'inviteur (socle).
    # 'coach_link'   : l'acceptation donne à l'inviteur (coach) une délégation
    #                  sur le compte de l'accepteur (client). Cf. docs/coaching_model.md.
    kind: Mapped[str] = mapped_column(
        String(16), default="collaborator", nullable=False
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','accepted','expired','revoked')",
            name="ck_invitation_status",
        ),
        CheckConstraint(
            "kind IN ('collaborator','coach_link')",
            name="ck_invitation_kind",
        ),
    )


class AuditLog(Base):
    """Journal des actions sur un compte partagé (exigence RGPD / santé)."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_identity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # JSON générique (portable SQLite/PG) ; JSONB côté Postgres via la migration.
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
