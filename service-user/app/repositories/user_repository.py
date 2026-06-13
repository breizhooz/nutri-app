"""Data-access layer for the users table.

All SQLAlchemy queries touching the User model live here (architecture rule:
no raw queries in routes or services).
"""

import uuid
from typing import Any, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Account, Invitation, Membership
from app.models.user import User


class UserRepository:
    """Repository encapsulating persistence operations for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.email))
        return list(result.scalars().all())

    async def list_personal_account_ids(self, user: User) -> list[uuid.UUID]:
        """Comptes personnels de l'identité (créés par elle, ou compte par défaut).

        Périmètre de l'effacement RGPD : on ne purge que les dossiers personnels,
        jamais les comptes où l'identité n'a qu'une adhésion (ex. client d'un
        coach).
        """
        conditions = [Account.created_by == user.id]
        if user.default_account_id is not None:
            conditions.append(Account.id == user.default_account_id)
        rows = await self.session.execute(select(Account.id).where(or_(*conditions)))
        return [r[0] for r in rows.all()]

    async def delete_personal_accounts(self, user: User) -> None:
        """Supprime le(s) compte(s) personnel(s) de l'identité avant de la supprimer.

        Sans ça, supprimer un utilisateur laisse son compte orphelin **et** les
        adhésions que d'autres détiennent dessus (ex. un coach) → ils continuent
        de le voir. Le DELETE sur ``accounts`` cascade les memberships (FK
        ondelete CASCADE), nettoyant aussi les liens de coaching.
        """
        account_ids = await self.list_personal_account_ids(user)
        if not account_ids:
            return

        # Lâche la référence users.default_account_id avant de supprimer le compte
        # (la FK n'est pas forcément ON DELETE SET NULL).
        user.default_account_id = None
        await self.session.flush()
        # Suppression explicite des dépendances (robuste SQLite + PG) : memberships
        # (dont les liens de coaching), invitations, puis les comptes eux-mêmes.
        await self.session.execute(
            delete(Membership).where(Membership.account_id.in_(account_ids))
        )
        await self.session.execute(
            delete(Invitation).where(Invitation.account_id.in_(account_ids))
        )
        await self.session.execute(delete(Account).where(Account.id.in_(account_ids)))
        await self.session.flush()

    async def delete(self, user: User) -> None:
        """Permanently remove a user account (and its personal account)."""
        await self.delete_personal_accounts(user)
        await self.session.delete(user)
        await self.session.commit()

    async def update_rights(
        self,
        user: User,
        *,
        user_admin: Optional[bool] = None,
        is_coach: Optional[bool] = None,
        user_right: Optional[dict[str, Any]] = None,
    ) -> User:
        """Persist a partial update of a user's RBAC fields.

        Only the provided (non-None) fields are modified.
        """
        if user_admin is not None:
            user.user_admin = user_admin
        if is_coach is not None:
            user.is_coach = is_coach
        if user_right is not None:
            user.user_right = user_right
        await self.session.commit()
        await self.session.refresh(user)
        return user
