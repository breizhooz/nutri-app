"""multicomptes phase 3 : invitations + audit_logs

Crée les tables de partage (invitations) et de journal d'audit (audit_logs).
Non destructive.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "role_code", sa.String(length=32), sa.ForeignKey("roles.code"),
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','expired','revoked')",
            name="ck_invitation_status",
        ),
    )
    op.create_index(
        "ix_invitations_email",
        "invitations",
        ["email"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_account_time",
        "audit_logs",
        ["account_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_account_time", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_table("invitations")
