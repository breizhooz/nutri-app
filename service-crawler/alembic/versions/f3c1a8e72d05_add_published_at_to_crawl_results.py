"""add published_at to crawl_results

Revision ID: f3c1a8e72d05
Revises: c3a9f7e2b4d1
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

revision = "f3c1a8e72d05"
down_revision = "c3a9f7e2b4d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crawl_results",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crawl_results", "published_at")
