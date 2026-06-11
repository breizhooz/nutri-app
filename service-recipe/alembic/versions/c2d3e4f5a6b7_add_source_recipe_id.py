"""coaching : recipes.source_recipe_id (provenance des recettes poussées)

Quand un coach pousse une recette dans le compte d'un client (copie one-shot,
cf. docs/coaching_model.md), la copie garde l'id de la recette source pour la
traçabilité et le garde anti-doublon. Non destructive.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("source_recipe_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_recipes_source_recipe_id", "recipes", ["source_recipe_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_recipes_source_recipe_id", table_name="recipes")
    op.drop_column("recipes", "source_recipe_id")
