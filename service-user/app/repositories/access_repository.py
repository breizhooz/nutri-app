"""Data-access layer for the multi-account access tables.

All SQLAlchemy queries touching memberships / role_scopes live here
(architecture rule: no raw queries in routes or services).
"""

import uuid
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.access import (
    Account,
    AuditLog,
    Invitation,
    Membership,
    RoleScope,
)
from app.models.user import User


class MembershipRepository:
    """Persistence operations for :class:`Membership`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(
        self, identity_id: uuid.UUID, account_id: uuid.UUID
    ) -> Optional[Membership]:
        """Return the active membership of an identity on an account, or None.

        Eager-loads scope overrides so the caller can compute effective scopes
        without a second round-trip.
        """
        result = await self.session.execute(
            select(Membership)
            .where(
                Membership.identity_id == identity_id,
                Membership.account_id == account_id,
                Membership.status == "active",
            )
            .options(selectinload(Membership.overrides))
        )
        return result.scalar_one_or_none()

    async def list_for_identity(
        self, identity_id: uuid.UUID
    ) -> list[tuple[Membership, Account]]:
        """List the identity's active memberships joined with their account.

        Soft-deleted accounts (``deleted_at`` set) are excluded.
        """
        result = await self.session.execute(
            select(Membership, Account)
            .join(Account, Membership.account_id == Account.id)
            .where(
                Membership.identity_id == identity_id,
                Membership.status == "active",
                Account.deleted_at.is_(None),
            )
            .order_by(Account.name)
        )
        return [(m, a) for m, a in result.all()]

    async def list_for_account(
        self, account_id: uuid.UUID
    ) -> list[tuple[Membership, User]]:
        """List a account's memberships joined with their identity (for email)."""
        result = await self.session.execute(
            select(Membership, User)
            .join(User, Membership.identity_id == User.id)
            .where(Membership.account_id == account_id)
            .order_by(Membership.created_at)
        )
        return [(m, u) for m, u in result.all()]

    async def get_by_id(self, membership_id: uuid.UUID) -> Optional[Membership]:
        result = await self.session.execute(
            select(Membership).where(Membership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def get_for_account(
        self, identity_id: uuid.UUID, account_id: uuid.UUID
    ) -> Optional[Membership]:
        """Membership of an identity on an account, any status."""
        result = await self.session.execute(
            select(Membership).where(
                Membership.identity_id == identity_id,
                Membership.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def roles_by_identity(self) -> dict[uuid.UUID, list[str]]:
        """Rôles de compte distincts par identité (memberships actifs).

        Sert à l'écran admin pour afficher le(s) rôle(s) d'un utilisateur.
        """
        result = await self.session.execute(
            select(Membership.identity_id, Membership.role_code)
            .where(Membership.status == "active")
            .distinct()
        )
        roles: dict[uuid.UUID, list[str]] = {}
        for identity_id, role_code in result.all():
            roles.setdefault(identity_id, []).append(role_code)
        return roles

    async def get_active_coach(
        self, account_id: uuid.UUID
    ) -> Optional[Membership]:
        """Coach actif d'un compte (modèle coach→client : 1 coach max)."""
        result = await self.session.execute(
            select(Membership).where(
                Membership.account_id == account_id,
                Membership.role_code == "COACH",
                Membership.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def count_active_owners(self, account_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Membership.id)).where(
                Membership.account_id == account_id,
                Membership.role_code == "OWNER",
                Membership.status == "active",
            )
        )
        return result.scalar_one()

    def add(self, membership: Membership) -> None:
        """Stage a new membership (no commit — caller owns the transaction)."""
        self.session.add(membership)


class InvitationRepository:
    """Persistence operations for :class:`Invitation`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, invitation: Invitation) -> None:
        self.session.add(invitation)

    async def get_by_token(self, token: str) -> Optional[Invitation]:
        result = await self.session.execute(
            select(Invitation).where(Invitation.token == token)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, invitation_id: uuid.UUID) -> Optional[Invitation]:
        result = await self.session.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    async def list_pending_for_account(
        self, account_id: uuid.UUID
    ) -> list[Invitation]:
        result = await self.session.execute(
            select(Invitation)
            .where(
                Invitation.account_id == account_id,
                Invitation.status == "pending",
            )
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())


class AuditRepository:
    """Persistence operations for :class:`AuditLog`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        actor_identity_id: Optional[uuid.UUID],
        account_id: Optional[uuid.UUID],
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Stage an audit line (no commit — caller owns the transaction)."""
        entry = AuditLog(
            actor_identity_id=actor_identity_id,
            account_id=account_id,
            action=action,
            payload=payload or {},
        )
        self.session.add(entry)
        return entry

    async def list_for_account(
        self, account_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.account_id == account_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())


class RoleScopeRepository:
    """Persistence operations for the role -> scopes reference data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scopes_for_role(self, role_code: str) -> set[str]:
        result = await self.session.execute(
            select(RoleScope.scope_code).where(RoleScope.role_code == role_code)
        )
        return set(result.scalars().all())
