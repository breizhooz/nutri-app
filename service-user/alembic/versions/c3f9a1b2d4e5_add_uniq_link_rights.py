"""add uniq_link rights to user_right

Revision ID: c3f9a1b2d4e5
Revises: b7d4f9a1c2e3
Create Date: 2026-05-31 17:00:00.000000
"""

from alembic import op


revision = "c3f9a1b2d4e5"
down_revision = "b7d4f9a1c2e3"
branch_labels = None
depends_on = None

_UNIQ_LINK_DEFAULT = '{"uniq_link": {"instagram": false, "web": false}}'


def upgrade() -> None:
    # Backfill : ajoute la clé uniq_link aux lignes qui ne l'ont pas encore,
    # sans écraser un éventuel uniq_link déjà présent.
    op.execute(
        f"""
        UPDATE users
        SET user_right = user_right || '{_UNIQ_LINK_DEFAULT}'::jsonb
        WHERE NOT (user_right ? 'uniq_link')
        """
    )


def downgrade() -> None:
    op.execute("UPDATE users SET user_right = user_right - 'uniq_link'")
