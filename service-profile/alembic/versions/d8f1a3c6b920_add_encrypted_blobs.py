"""add encrypted_blobs (coffre opaque E2E zero-knowledge)

Phase 2 de l'épic E2E : table de blobs chiffrés côté client. Le serveur ne stocke
que du ciphertext opaque + l'enveloppe d'adressage (account_id, collection,
ref_key) + content_version pour la concurrence multi-appareils. Aucune donnée de
santé en clair. Cf. docs/rgpd/plan_dpo.md.

Revision ID: d8f1a3c6b920
Revises: a7c1e9d2b4f8
Create Date: 2026-06-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8f1a3c6b920"
down_revision: Union[str, None] = "a7c1e9d2b4f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encrypted_blobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection", sa.String(length=64), nullable=False),
        sa.Column("ref_key", sa.String(length=128), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "collection", "ref_key", name="uq_encrypted_blobs_addr"
        ),
    )
    op.create_index(
        "ix_encrypted_blobs_account_id", "encrypted_blobs", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_encrypted_blobs_account_id", table_name="encrypted_blobs")
    op.drop_table("encrypted_blobs")
