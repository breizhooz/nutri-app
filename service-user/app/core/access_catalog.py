"""Single source of truth for the RBAC reference data (roles / scopes).

The Alembic migration seeds these same values into Postgres with a frozen,
inlined copy (migrations must stay reproducible across history). This module is
the *runtime/test* source: ``seed_access`` is idempotent and used by the test
suite (which builds the schema with ``Base.metadata.create_all``, not Alembic).

Keep the two copies in sync; the values are stable reference data taken from
``docs/roles/etude_tk_role.md`` §2.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Role, RoleScope, Scope

# (code, label)
SCOPES: list[tuple[str, str]] = [
    ("recipe:read", "Voir les recettes"),
    ("recipe:write", "Modifier les recettes"),
    ("plan:read", "Voir les plans"),
    ("plan:write", "Modifier les plans"),
    ("profile:read", "Voir le profil"),
    ("profile:write", "Modifier le profil"),
    ("journal:read", "Voir le journal"),
    ("journal:write", "Écrire dans le journal"),
    ("member:manage", "Gérer les membres"),
    ("account:delete", "Supprimer le compte"),
]

# (code, label, rank)
ROLES: list[tuple[str, str, int]] = [
    ("OWNER", "Propriétaire", 100),
    ("ADMIN", "Administrateur", 80),
    # COACH : rôle délégué du modèle coach→client (cf. docs/coaching_model.md).
    # Rang entre ADMIN et EDITOR : un OWNER (le client) peut toujours le révoquer.
    ("COACH", "Coach", 70),
    ("EDITOR", "Éditeur", 60),
    ("CONTRIBUTOR", "Contributeur", 40),
    ("VIEWER", "Lecteur", 20),
]

_ALL_SCOPES: set[str] = {code for code, _ in SCOPES}

# role_code -> set of scope codes
ROLE_SCOPES: dict[str, set[str]] = {
    # OWNER: everything
    "OWNER": set(_ALL_SCOPES),
    # ADMIN: everything except deleting the account
    "ADMIN": _ALL_SCOPES - {"account:delete"},
    # COACH: gère le suivi du client (recettes/menu/profil/objectifs) mais ne
    # touche ni au journal (vécu du client), ni aux membres, ni à la suppression.
    "COACH": {
        "recipe:read",
        "recipe:write",
        "plan:read",
        "plan:write",
        "profile:read",
        "profile:write",
        "journal:read",
    },
    # EDITOR: read everywhere + write business content
    "EDITOR": {
        "recipe:read",
        "recipe:write",
        "plan:read",
        "plan:write",
        "journal:read",
        "journal:write",
        "profile:read",
    },
    # CONTRIBUTOR: read everywhere + write the journal only
    "CONTRIBUTOR": {
        "recipe:read",
        "plan:read",
        "profile:read",
        "journal:read",
        "journal:write",
    },
    # VIEWER: read only
    "VIEWER": {"recipe:read", "plan:read", "profile:read", "journal:read"},
}


def role_scope_rows() -> list[tuple[str, str]]:
    """Flatten ROLE_SCOPES into ``(role_code, scope_code)`` rows (sorted)."""
    rows: list[tuple[str, str]] = []
    for role_code, scopes in ROLE_SCOPES.items():
        for scope_code in sorted(scopes):
            rows.append((role_code, scope_code))
    return rows


async def seed_access(session: AsyncSession) -> None:
    """Idempotently insert the roles/scopes/role_scopes reference data.

    Safe to call on an already-seeded database: existing primary keys are
    skipped. Does not commit — the caller controls the transaction.
    """
    existing_scopes = set((await session.execute(select(Scope.code))).scalars().all())
    for code, label in SCOPES:
        if code not in existing_scopes:
            session.add(Scope(code=code, label=label))

    existing_roles = set((await session.execute(select(Role.code))).scalars().all())
    for code, label, rank in ROLES:
        if code not in existing_roles:
            session.add(Role(code=code, label=label, rank=rank))

    await session.flush()

    existing_rs = set(
        (await session.execute(select(RoleScope.role_code, RoleScope.scope_code))).all()
    )
    for role_code, scope_code in role_scope_rows():
        if (role_code, scope_code) not in existing_rs:
            session.add(RoleScope(role_code=role_code, scope_code=scope_code))

    await session.flush()
