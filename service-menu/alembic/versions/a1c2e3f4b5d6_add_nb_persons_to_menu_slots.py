"""add nb_persons to menu_slots

Revision ID: a1c2e3f4b5d6
Revises: 2816abe34c7b
Create Date: 2026-05-29 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a1c2e3f4b5d6"
down_revision = "2816abe34c7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "menu_slots",
        sa.Column(
            "nb_persons",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("menu_slots", "nb_persons")
