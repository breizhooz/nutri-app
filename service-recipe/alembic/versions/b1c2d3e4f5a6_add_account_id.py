"""add account_id to recipes (multi-account frontier, option 2)

Phase 2 de la couche multicomptes : les recettes deviennent privées par compte
(account_id = act_account du JWT). Nullable ; backfillé cross-DB depuis les
memberships OWNER de service-user (scripts/backfill_account_id.py) puis réindex
ES. NOT NULL différé.

Revision ID: b1c2d3e4f5a6
Revises: f9b3a7c4d2e1
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "f9b3a7c4d2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes", sa.Column("account_id", sa.String(length=36), nullable=True)
    )
    op.create_index("ix_recipes_account_id", "recipes", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_recipes_account_id", table_name="recipes")
    op.drop_column("recipes", "account_id")
