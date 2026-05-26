"""add_nutrition_columns_to_recipe

Revision ID: f3a8c1d2e9b7
Revises: 13624cb5abaa
Create Date: 2026-05-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a8c1d2e9b7"
down_revision: Union[str, None] = "b2d4e8f1c6a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("calories_per_serving", sa.Float(), nullable=True))
    op.add_column("recipes", sa.Column("proteins_per_serving", sa.Float(), nullable=True))
    op.add_column("recipes", sa.Column("carbs_per_serving", sa.Float(), nullable=True))
    op.add_column("recipes", sa.Column("fats_per_serving", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipes", "fats_per_serving")
    op.drop_column("recipes", "carbs_per_serving")
    op.drop_column("recipes", "proteins_per_serving")
    op.drop_column("recipes", "calories_per_serving")
