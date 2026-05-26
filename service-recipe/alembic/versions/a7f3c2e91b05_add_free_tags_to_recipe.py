"""add_free_tags_to_recipe

Revision ID: a7f3c2e91b05
Revises: 13624cb5abaa
Create Date: 2026-05-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f3c2e91b05"
down_revision: Union[str, None] = "e168ea5e4bdd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("free_tags", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("recipes", "free_tags")
