"""video_url_text

Revision ID: 85db51d9cdec
Revises: e14722443160
Create Date: 2026-05-25 18:29:44.914539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '85db51d9cdec'
down_revision: Union[str, None] = 'e14722443160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "crawl_results",
        "video_url",
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "crawl_results",
        "video_url",
        type_=sa.String(1000),
        existing_nullable=True,
    )