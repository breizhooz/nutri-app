"""add nb_persons to menu_slots

Revision ID: c3f1a2b4d5e6
Revises: 7d2f9a4c1e80
Create Date: 2026-05-28 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "c3f1a2b4d5e6"
down_revision = "7d2f9a4c1e80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "menu_slots",
        sa.Column("nb_persons", sa.Integer(), nullable=False, server_default="1"),
    )
    # Backfill : chaque slot hérite du nb_persons de son menu parent.
    op.execute(
        "UPDATE menu_slots SET nb_persons = wm.nb_persons "
        "FROM weekly_menus wm WHERE wm.id = menu_slots.menu_id"
    )
    op.alter_column("menu_slots", "nb_persons", server_default=None)


def downgrade() -> None:
    op.drop_column("menu_slots", "nb_persons")
