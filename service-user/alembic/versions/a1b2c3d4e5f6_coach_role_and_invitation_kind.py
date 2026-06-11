"""coaching : rôle COACH + invitations.kind

Ajoute le rôle délégué ``COACH`` (modèle coach→client, cf. docs/coaching_model.md)
et le champ ``invitations.kind`` (``collaborator`` | ``coach_link``) qui distingue
le partage collaboratif du lien de coaching. Un index unique partiel garantit un
seul coach actif par compte client. Non destructive.

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-06-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

# Snapshot figé (les migrations ne doivent pas dépendre du code applicatif).
_COACH_SCOPES = [
    "recipe:read",
    "recipe:write",
    "plan:read",
    "plan:write",
    "profile:read",
    "profile:write",
    "journal:read",
]


def upgrade() -> None:
    # 1. Rôle COACH (rang 70, entre ADMIN=80 et EDITOR=60).
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("code", sa.String),
            sa.column("label", sa.Text),
            sa.column("rank", sa.Integer),
        ),
        [{"code": "COACH", "label": "Coach", "rank": 70}],
    )
    op.bulk_insert(
        sa.table(
            "role_scopes",
            sa.column("role_code", sa.String),
            sa.column("scope_code", sa.String),
        ),
        [{"role_code": "COACH", "scope_code": s} for s in _COACH_SCOPES],
    )

    # 2. invitations.kind (défaut 'collaborator' → backward compatible).
    op.add_column(
        "invitations",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="collaborator",
        ),
    )
    op.create_check_constraint(
        "ck_invitation_kind",
        "invitations",
        "kind IN ('collaborator','coach_link')",
    )

    # 3. Un seul coach actif par compte client (garde-fou DB, en plus du service).
    op.create_index(
        "uq_one_active_coach",
        "memberships",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("role_code = 'COACH' AND status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_one_active_coach", table_name="memberships")
    op.drop_constraint("ck_invitation_kind", "invitations", type_="check")
    op.drop_column("invitations", "kind")
    op.execute("DELETE FROM role_scopes WHERE role_code = 'COACH'")
    op.execute("DELETE FROM roles WHERE code = 'COACH'")
