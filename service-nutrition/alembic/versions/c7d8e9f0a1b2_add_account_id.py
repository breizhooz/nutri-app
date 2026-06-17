"""add account_id to macro_errors (multi-account frontier)

Phase 2 de la couche multicomptes : les macro_errors (résolution d'ingrédients
par compte) sont partitionnés par account_id. Renseigné par le flux
recipe→/calculate qui propage account_id. Nullable ; backfill cross-DB depuis
les memberships OWNER de service-user. NOT NULL différé.

Revision ID: c7d8e9f0a1b2
Revises: bb9d947887f2
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "bb9d947887f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "macro_errors",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_macro_errors_account_id", "macro_errors", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_macro_errors_account_id", table_name="macro_errors")
    op.drop_column("macro_errors", "account_id")
