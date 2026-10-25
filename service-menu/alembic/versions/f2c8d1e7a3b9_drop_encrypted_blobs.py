"""supprime le coffre chiffré des menus (allègement RGPD)

Les menus sont de nouveau générés et stockés côté serveur (``weekly_menus``).
La table ``encrypted_blobs`` (menus chiffrés côté client, illisibles par le
serveur) est supprimée avec son contenu — décision utilisateur du 2026-10-24.
Le downgrade recrée une table vide.

Revision ID: f2c8d1e7a3b9
Revises: b1c2d3e4f5a6
Create Date: 2026-10-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2c8d1e7a3b9"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_encrypted_blobs_account_id", table_name="encrypted_blobs")
    op.drop_table("encrypted_blobs")


def downgrade() -> None:
    op.create_table(
        "encrypted_blobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
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
    op.create_index("ix_encrypted_blobs_account_id", "encrypted_blobs", ["account_id"])
