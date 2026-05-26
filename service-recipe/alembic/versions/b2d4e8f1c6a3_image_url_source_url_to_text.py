"""image_url_source_url_to_text

Revision ID: b2d4e8f1c6a3
Revises: a7f3c2e91b05
Create Date: 2026-05-26 11:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4e8f1c6a3"
down_revision: Union[str, None] = "a7f3c2e91b05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("recipes", "image_url", type_=sa.Text(), existing_nullable=True)
    op.alter_column("recipes", "source_url", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("recipes", "image_url", type_=sa.String(500), existing_nullable=True)
    op.alter_column("recipes", "source_url", type_=sa.String(500), existing_nullable=True)
