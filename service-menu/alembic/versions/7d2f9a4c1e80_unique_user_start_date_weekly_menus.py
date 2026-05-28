"""unique (user_id, start_date) on weekly_menus + dedup

Revision ID: 7d2f9a4c1e80
Revises: 2816abe34c7b
Create Date: 2026-05-28 16:00:00.000000
"""

from alembic import op

revision = "7d2f9a4c1e80"
down_revision = "2816abe34c7b"
branch_labels = None
depends_on = None


_DUP_IDS = """
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY user_id, start_date
            ORDER BY created_at DESC, id DESC
        ) AS rn
        FROM weekly_menus
    ) d WHERE d.rn > 1
"""


def upgrade() -> None:
    # Dédoublonnage préalable : on garde le menu le plus récent par (user_id, start_date).
    # Les slots n'ont pas de cascade SQL → on les supprime d'abord.
    op.execute(f"DELETE FROM menu_slots WHERE menu_id IN ({_DUP_IDS})")
    op.execute(f"DELETE FROM weekly_menus WHERE id IN ({_DUP_IDS})")
    op.create_unique_constraint(
        "uq_weekly_menus_user_start_date",
        "weekly_menus",
        ["user_id", "start_date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_weekly_menus_user_start_date", "weekly_menus", type_="unique"
    )
