"""add_spoonacular_recipe_cache

Revision ID: f9b3a7c4d2e1
Revises: a1c9f4e2b7d8
Create Date: 2026-06-03 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9b3a7c4d2e1"
down_revision: Union[str, None] = "a1c9f4e2b7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spoonacular_recipe_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spoonacular_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index unique sur l'id Spoonacular : sert à l'upsert (1 ligne par recette).
    op.create_index(
        op.f("ix_spoonacular_recipe_cache_spoonacular_id"),
        "spoonacular_recipe_cache",
        ["spoonacular_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_spoonacular_recipe_cache_spoonacular_id"),
        table_name="spoonacular_recipe_cache",
    )
    op.drop_table("spoonacular_recipe_cache")
