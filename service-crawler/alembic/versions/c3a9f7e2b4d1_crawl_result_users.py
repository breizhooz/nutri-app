"""crawl_result_users — relation 1 post → N users

Revision ID: c3a9f7e2b4d1
Revises: 85db51d9cdec
Create Date: 2026-05-25 23:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3a9f7e2b4d1"
down_revision: Union[str, None] = "85db51d9cdec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Supprimer les colonnes per-user de crawl_results
    op.drop_column("crawl_results", "validate_date")
    op.drop_column("crawl_results", "validate_by")
    op.drop_column("crawl_results", "status")
    op.drop_column("crawl_results", "user_id")

    # 2. Retirer le FK source_id de crawl_results (source est maintenant sur crawl_result_users)
    op.drop_constraint(
        "crawl_results_source_id_fkey", "crawl_results", type_="foreignkey"
    )
    op.drop_column("crawl_results", "source_id")

    # 3. Dédoublonner url_origin avant d'ajouter la contrainte UNIQUE
    op.execute("""
        DELETE FROM crawl_results
        WHERE id NOT IN (
            SELECT DISTINCT ON (url_origin) id
            FROM crawl_results
            ORDER BY url_origin, created_at DESC
        )
    """)
    op.create_unique_constraint(
        "uq_crawl_results_url_origin", "crawl_results", ["url_origin"]
    )

    # 4. Créer la table crawl_result_users
    op.create_table(
        "crawl_result_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("validate_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validate_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["result_id"], ["crawl_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["crawl_sources.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("result_id", "user_id", name="uq_crawl_result_user"),
    )


def downgrade() -> None:
    op.drop_table("crawl_result_users")

    op.drop_constraint("uq_crawl_results_url_origin", "crawl_results", type_="unique")

    op.add_column(
        "crawl_results",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "crawl_results_source_id_fkey",
        "crawl_results",
        "crawl_sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "crawl_results",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "crawl_results",
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="waiting"
        ),
    )
    op.add_column(
        "crawl_results",
        sa.Column("validate_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "crawl_results",
        sa.Column("validate_date", sa.DateTime(timezone=True), nullable=True),
    )
