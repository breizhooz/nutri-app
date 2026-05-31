"""add_comment_rating_to_recipe

Revision ID: d4b6f2a9c1e7
Revises: c5e7a1b9d3f2
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b6f2a9c1e7"
down_revision: Union[str, None] = "c5e7a1b9d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("recipes", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipes", "rating")
    op.drop_column("recipes", "comment")
