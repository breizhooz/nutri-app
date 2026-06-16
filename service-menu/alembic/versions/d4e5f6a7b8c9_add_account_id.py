"""add account_id to weekly_menus (multi-account frontier)

Phase 2 de la couche multicomptes : les menus (plans) sont partitionnés par
account_id (= act_account du JWT). Nullable ; backfillé cross-DB depuis les
memberships OWNER de service-user (scripts/backfill_account_id.py). NOT NULL
différé.

Revision ID: d4e5f6a7b8c9
Revises: c3f1a2b4d5e6
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3f1a2b4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weekly_menus", sa.Column("account_id", sa.String(length=36), nullable=True)
    )
    op.create_index("ix_weekly_menus_account_id", "weekly_menus", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_weekly_menus_account_id", table_name="weekly_menus")
    op.drop_column("weekly_menus", "account_id")
