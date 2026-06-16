"""multi-account socle: accounts/memberships/roles/scopes + 1:1 backfill

Phase 1 of the CRM multi-account layer (see docs/roles/). Non destructive:
creates the access tables, seeds the roles/scopes catalogue, and turns every
existing user into 1 account + 1 OWNER membership, wiring users.default_account_id.

The roles/scopes seed below is a FROZEN snapshot — it intentionally duplicates
app/core/access_catalog.py so the migration stays reproducible across history
even if the runtime catalogue evolves later.

Revision ID: e1f2a3b4c5d6
Revises: c3f9a1b2d4e5
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e1f2a3b4c5d6"
down_revision = "c3f9a1b2d4e5"
branch_labels = None
depends_on = None


# --- Frozen seed snapshot ---------------------------------------------------
_SCOPES: list[tuple[str, str]] = [
    ("recipe:read", "Voir les recettes"),
    ("recipe:write", "Modifier les recettes"),
    ("plan:read", "Voir les plans"),
    ("plan:write", "Modifier les plans"),
    ("profile:read", "Voir le profil"),
    ("profile:write", "Modifier le profil"),
    ("journal:read", "Voir le journal"),
    ("journal:write", "Écrire dans le journal"),
    ("member:manage", "Gérer les membres"),
    ("account:delete", "Supprimer le compte"),
]

_ROLES: list[tuple[str, str, int]] = [
    ("OWNER", "Propriétaire", 100),
    ("ADMIN", "Administrateur", 80),
    ("EDITOR", "Éditeur", 60),
    ("CONTRIBUTOR", "Contributeur", 40),
    ("VIEWER", "Lecteur", 20),
]

_ALL = {c for c, _ in _SCOPES}
_ROLE_SCOPES: dict[str, set[str]] = {
    "OWNER": set(_ALL),
    "ADMIN": _ALL - {"account:delete"},
    "EDITOR": {
        "recipe:read",
        "recipe:write",
        "plan:read",
        "plan:write",
        "journal:read",
        "journal:write",
        "profile:read",
    },
    "CONTRIBUTOR": {
        "recipe:read",
        "plan:read",
        "profile:read",
        "journal:read",
        "journal:write",
    },
    "VIEWER": {"recipe:read", "plan:read", "profile:read", "journal:read"},
}


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # --- 1. Reference tables (roles, scopes) --------------------------------
    op.create_table(
        "roles",
        sa.Column("code", sa.String(length=32), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
    )
    op.create_table(
        "scopes",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
    )
    op.create_table(
        "role_scopes",
        sa.Column(
            "role_code",
            sa.String(length=32),
            sa.ForeignKey("roles.code", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "scope_code",
            sa.String(length=64),
            sa.ForeignKey("scopes.code", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- 2. Accounts --------------------------------------------------------
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "type", sa.String(length=20), nullable=False, server_default="personal"
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('personal','managed')", name="ck_account_type"),
    )

    # --- 3. Memberships -----------------------------------------------------
    op.create_table(
        "memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_code",
            sa.String(length=32),
            sa.ForeignKey("roles.code"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("identity_id", "account_id", name="uq_membership"),
        sa.CheckConstraint(
            "status IN ('active','suspended','revoked')", name="ck_membership_status"
        ),
    )
    op.create_index(
        "ix_memberships_account",
        "memberships",
        ["account_id"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_memberships_identity",
        "memberships",
        ["identity_id"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # --- 4. Per-membership scope overrides ----------------------------------
    op.create_table(
        "membership_scope_overrides",
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memberships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "scope_code",
            sa.String(length=64),
            sa.ForeignKey("scopes.code", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("effect", sa.String(length=8), nullable=False),
        sa.CheckConstraint("effect IN ('grant','deny')", name="ck_override_effect"),
    )

    # --- 5. Seed roles / scopes / role_scopes -------------------------------
    op.bulk_insert(
        sa.table(
            "scopes",
            sa.column("code", sa.String),
            sa.column("label", sa.Text),
        ),
        [{"code": c, "label": label} for c, label in _SCOPES],
    )
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("code", sa.String),
            sa.column("label", sa.Text),
            sa.column("rank", sa.Integer),
        ),
        [{"code": c, "label": label, "rank": rank} for c, label, rank in _ROLES],
    )
    op.bulk_insert(
        sa.table(
            "role_scopes",
            sa.column("role_code", sa.String),
            sa.column("scope_code", sa.String),
        ),
        [
            {"role_code": role, "scope_code": scope}
            for role, scopes in _ROLE_SCOPES.items()
            for scope in sorted(scopes)
        ],
    )

    # --- 6. users.default_account_id (nullable, FK added after backfill) -----
    op.add_column(
        "users",
        sa.Column("default_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # --- 7. Backfill 1:1 — each user -> 1 account + 1 OWNER membership -------
    op.execute(
        """
        INSERT INTO accounts (id, name, type, created_by, created_at)
        SELECT gen_random_uuid(), u.email, 'personal', u.id, now()
        FROM users u;
        """
    )
    op.execute(
        """
        INSERT INTO memberships
            (id, identity_id, account_id, role_code, status, created_at)
        SELECT gen_random_uuid(), a.created_by, a.id, 'OWNER', 'active', now()
        FROM accounts a;
        """
    )
    op.execute(
        """
        UPDATE users u
        SET default_account_id = a.id
        FROM accounts a
        WHERE a.created_by = u.id;
        """
    )

    # --- 8. Deferred FK users.default_account_id -> accounts.id --------------
    op.create_foreign_key(
        "fk_users_default_account",
        "users",
        "accounts",
        ["default_account_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_default_account", "users", type_="foreignkey")
    op.drop_column("users", "default_account_id")
    op.drop_table("membership_scope_overrides")
    op.drop_index("ix_memberships_identity", table_name="memberships")
    op.drop_index("ix_memberships_account", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("accounts")
    op.drop_table("role_scopes")
    op.drop_table("scopes")
    op.drop_table("roles")
