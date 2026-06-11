"""add account_id to profiles (multi-account frontier)

Phase 2 of the CRM multi-account layer: the dossier (profiles) becomes
partitioned by account_id (= act_account of the JWT) instead of user_id.
Nullable here; backfilled cross-DB from service-user OWNER memberships
(see service-profile/scripts/backfill_account_id.py), NOT NULL deferred.

Revision ID: a7c1e9d2b4f8
Revises: c7e2f4b8a1d3
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7c1e9d2b4f8"
down_revision: Union[str, None] = "c7e2f4b8a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_profiles_account_id", "profiles", ["account_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_account_id", table_name="profiles")
    op.drop_column("profiles", "account_id")
