"""add_image_search_cache

Revision ID: a1c9f4e2b7d8
Revises: d4b6f2a9c1e7
Create Date: 2026-06-03 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c9f4e2b7d8"
down_revision: Union[str, None] = "d4b6f2a9c1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_search_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=300), nullable=False),
        sa.Column(
            "suggestions",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index unique exact : sert à l'upsert (1 ligne par mot-clé normalisé).
    op.create_index(
        op.f("ix_image_search_cache_keyword"),
        "image_search_cache",
        ["keyword"],
        unique=True,
    )

    # Réutilisation du cache par recherche fulltext français (tsvector) : index GIN
    # qui accélère le `@@`. Pas de trigramme volontairement — la similarité sur titre
    # entier provoquait des collisions entre plats partageant un suffixe boilerplate.
    op.execute(
        "CREATE INDEX ix_image_search_cache_keyword_tsv "
        "ON image_search_cache "
        "USING gin (to_tsvector('french', keyword))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_search_cache_keyword_tsv")
    op.drop_index(
        op.f("ix_image_search_cache_keyword"), table_name="image_search_cache"
    )
    op.drop_table("image_search_cache")
