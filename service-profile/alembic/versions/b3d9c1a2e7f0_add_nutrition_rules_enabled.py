"""add nutrition_rules_enabled to profiles

Revision ID: b3d9c1a2e7f0
Revises: 1fb75218d795
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3d9c1a2e7f0"
down_revision: Union[str, None] = "1fb75218d795"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "nutrition_rules_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "nutrition_rules_enabled")
