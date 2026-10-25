"""profil nutritionnel en clair, sans coffre chiffré ni données médicales

Allègement RGPD (2026-10-24) : fin du coffre E2E côté client.
  • crée ``nutrition_profiles`` (un par compte : objectif, régime, préférences,
    aliments exclus, cibles calculées sur l'appareil) ;
  • supprime ``encrypted_blobs`` ET son contenu (profils santé chiffrés,
    illisibles par le serveur) — décision utilisateur : ressaisie du profil.

Le downgrade recrée une table ``encrypted_blobs`` vide : les blobs supprimés ne
sont pas récupérables.

Revision ID: e9b4c2d7f1a0
Revises: c4f7e1a9b302
Create Date: 2026-10-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e9b4c2d7f1a0"
down_revision: Union[str, None] = "c4f7e1a9b302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nutrition_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("main_goal", sa.String(length=25), nullable=False),
        sa.Column("diet_type", sa.String(length=15), nullable=False),
        sa.Column("diet_type_other", sa.String(length=100), nullable=True),
        sa.Column("meals_per_day", sa.SmallInteger(), nullable=True),
        sa.Column("snacks_per_day", sa.SmallInteger(), nullable=True),
        sa.Column("practices_if", sa.Boolean(), nullable=False),
        sa.Column("fasting_window_hours", sa.SmallInteger(), nullable=True),
        sa.Column("cooking_level", sa.String(length=15), nullable=True),
        sa.Column("cooking_time_available", sa.String(length=15), nullable=True),
        sa.Column("cooking_for", sa.String(length=15), nullable=True),
        sa.Column("budget_per_day_eur", sa.Numeric(7, 2), nullable=True),
        sa.Column("excluded_foods", sa.JSON(), nullable=False),
        sa.Column("nutrition_rules_enabled", sa.Boolean(), nullable=False),
        sa.Column("rules_variety_pct", sa.Float(), nullable=False),
        sa.Column("rules_override_calories", sa.Integer(), nullable=True),
        sa.Column("rules_override_proteines", sa.Integer(), nullable=True),
        sa.Column("target_calories_kcal", sa.Integer(), nullable=True),
        sa.Column("target_proteins_g", sa.Integer(), nullable=True),
        sa.Column("target_carbs_g", sa.Integer(), nullable=True),
        sa.Column("target_fats_g", sa.Integer(), nullable=True),
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
    )
    op.create_index(
        "ix_nutrition_profiles_account_id",
        "nutrition_profiles",
        ["account_id"],
        unique=True,
    )
    op.drop_index("ix_encrypted_blobs_account_id", table_name="encrypted_blobs")
    op.drop_table("encrypted_blobs")


def downgrade() -> None:
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
    op.create_index("ix_encrypted_blobs_account_id", "encrypted_blobs", ["account_id"])
    op.drop_index("ix_nutrition_profiles_account_id", table_name="nutrition_profiles")
    op.drop_table("nutrition_profiles")
