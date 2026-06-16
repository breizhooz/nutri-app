"""drop cleartext health tables (bascule E2E zero-knowledge, Phase 5)

Toute la santé en clair migre côté client dans le coffre chiffré (table opaque
``encrypted_blobs``, conservée). On supprime DÉFINITIVEMENT les tables de santé
en clair : profil, allergies, aliments exclus, blessures, conditions médicales,
médicaments, mode de vie, préférences nutritionnelles, profil sportif, métriques
de performance, composition et mesures corporelles.

⚠️ MIGRATION DESTRUCTIVE ET IRRÉVERSIBLE — les données en clair sont perdues
(c'est le but : zero-knowledge). Cf. docs/rgpd/plan_dpo.md §8 phase 5.

Revision ID: c4f7e1a9b302
Revises: d8f1a3c6b920
Create Date: 2026-06-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4f7e1a9b302"
down_revision: Union[str, None] = "d8f1a3c6b920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables filles d'abord, puis la table racine ``profiles``.
_HEALTH_TABLES = (
    "body_composition_snapshots",
    "body_measurements_snapshots",
    "excluded_foods",
    "food_allergies",
    "injuries",
    "lifestyle_profiles",
    "medical_conditions",
    "medications",
    "nutrition_preferences",
    "performance_metrics",
    "sports_profiles",
    "profiles",
)


def upgrade() -> None:
    for table in _HEALTH_TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')


def downgrade() -> None:
    raise NotImplementedError(
        "Migration irréversible : les tables de santé en clair ont été supprimées "
        "définitivement lors de la bascule E2E zero-knowledge (Phase 5)."
    )
