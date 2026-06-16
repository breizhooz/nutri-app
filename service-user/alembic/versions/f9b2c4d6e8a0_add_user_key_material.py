"""add user_key_material (enveloppe de clés E2E zero-knowledge)

Phase 3 de l'épic E2E : stockage par utilisateur des éléments opaques (salt,
params Argon2id, wrapped_uk, recovery_salt, wrapped_uk_recovery) calculés côté
client. Le serveur ne voit jamais de clé ni de secret. Cf. docs/rgpd/plan_dpo.md.

Revision ID: f9b2c4d6e8a0
Revises: e6f7a8b9c0d1
Create Date: 2026-06-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f9b2c4d6e8a0"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("user_key_material")
