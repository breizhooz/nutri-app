"""add rules adjustment defaults to nutrition_preferences

Revision ID: c7e2f4b8a1d3
Revises: b3d9c1a2e7f0
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e2f4b8a1d3"
down_revision: Union[str, None] = "b3d9c1a2e7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "nutrition_preferences",
        sa.Column(
            "rules_aggressiveness",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column(
        "nutrition_preferences",
        sa.Column(
            "rules_variety_pct",
            sa.Float(),
            nullable=False,
            server_default="0.1",
        ),
    )
    op.add_column(
        "nutrition_preferences",
        sa.Column("rules_override_calories", sa.Integer(), nullable=True),
    )
    op.add_column(
        "nutrition_preferences",
        sa.Column("rules_override_proteines", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("nutrition_preferences", "rules_override_proteines")
    op.drop_column("nutrition_preferences", "rules_override_calories")
    op.drop_column("nutrition_preferences", "rules_variety_pct")
    op.drop_column("nutrition_preferences", "rules_aggressiveness")
