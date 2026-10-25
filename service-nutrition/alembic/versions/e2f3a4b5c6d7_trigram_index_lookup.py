"""index trigramme du rapprochement ingrédient → Ciqual

Sans index, chaque lookup recalculait la similarité sur tous les aliments
(~82 ms de CPU PostgreSQL par appel, mesuré sur 3 484 aliments). Les index GIN
``gin_trgm_ops`` sur le nom normalisé permettent à l'opérateur ``<%``
(word_similarity ≥ seuil) de ne lire que les candidats.

``unaccent`` n'est pas IMMUTABLE (il dépend du dictionnaire et du search_path) :
indexer une expression exige une fonction IMMUTABLE, d'où le wrapper
``f_unaccent`` qui fige le dictionnaire (schéma explicite).

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


F_UNACCENT = """
CREATE OR REPLACE FUNCTION public.f_unaccent(text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
$$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_nutrition_items_nom_fr_trgm ON nutrition_items "
    "USING gin (public.f_unaccent(lower(nom_fr)) gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS ix_nutrition_items_nom_en_trgm ON nutrition_items "
    "USING gin (public.f_unaccent(lower(coalesce(nom_en, ''))) gin_trgm_ops)",
]


def upgrade() -> None:
    op.execute(F_UNACCENT)
    for statement in INDEXES:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_nutrition_items_nom_en_trgm")
    op.execute("DROP INDEX IF EXISTS ix_nutrition_items_nom_fr_trgm")
    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent(text)")
