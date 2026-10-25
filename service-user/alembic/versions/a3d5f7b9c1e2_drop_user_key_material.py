"""supprime le matériel de clés E2E (allègement RGPD)

Fin du coffre chiffré côté client (2026-10-24) : plus de passphrase ni de code
de récupération. La table ``user_key_material`` (sel, paramètres KDF, clés
enveloppées) est supprimée avec son contenu. Le downgrade recrée une table vide.

Revision ID: a3d5f7b9c1e2
Revises: f9b2c4d6e8a0
Create Date: 2026-10-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3d5f7b9c1e2"
down_revision: Union[str, None] = "f9b2c4d6e8a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("user_key_material")


def downgrade() -> None:
    op.create_table(
        "user_key_material",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("salt", sa.LargeBinary(), nullable=False),
        sa.Column("kdf_memory_mib", sa.Integer(), nullable=False),
        sa.Column("kdf_iterations", sa.Integer(), nullable=False),
        sa.Column("kdf_parallelism", sa.Integer(), nullable=False),
        sa.Column("wrapped_uk", sa.LargeBinary(), nullable=False),
        sa.Column("recovery_salt", sa.LargeBinary(), nullable=False),
        sa.Column("wrapped_uk_recovery", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
