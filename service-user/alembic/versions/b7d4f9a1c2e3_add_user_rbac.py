"""add RBAC fields (user_admin, user_right) to users

Revision ID: b7d4f9a1c2e3
Revises: d87193e45fe3
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b7d4f9a1c2e3"
down_revision = "d87193e45fe3"
branch_labels = None
depends_on = None

_USER_RIGHT_DEFAULT = '{"crawl": {"instagram": false, "web": false}}'


def upgrade() -> None:
    # NOT NULL + server_default → les lignes existantes sont backfillées
    # automatiquement par Postgres avec les valeurs par défaut.
    op.add_column(
        "users",
        sa.Column(
            "user_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "user_right",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(f"'{_USER_RIGHT_DEFAULT}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "user_right")
    op.drop_column("users", "user_admin")
