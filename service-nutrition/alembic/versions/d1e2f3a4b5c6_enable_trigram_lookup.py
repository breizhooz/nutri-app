"""enable pg_trgm + unaccent for the nutrition lookup (replaces Elasticsearch)

Le rapprochement approximatif ingrédient → référentiel Ciqual passe
d'Elasticsearch (index ``nutrition_items``) à PostgreSQL :
``word_similarity(unaccent(lower(q)), unaccent(lower(nom_fr)))``.
Les deux extensions sont « trusted » (PG ≥ 13) : le rôle propriétaire de la
base peut les créer sans superutilisateur.

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-10-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
