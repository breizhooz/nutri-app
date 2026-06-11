"""Business logic for managing the members of a shared account (phase 3)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Membership, Role
from app.models.user import User
from app.repositories.access_repository import AuditRepository, MembershipRepository
from app.services.access_errors import LastOwner, MembershipNotFound, RankTooHigh


class MemberService:
    """List and mutate memberships of an account, with CRM guardrails."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._members = MembershipRepository(session)
        self._audit = AuditRepository(session)

    async def list_members(
        self, account_id: uuid.UUID
    ) -> list[tuple[Membership, User]]:
        return await self._members.list_for_account(account_id)

    async def _role_rank(self, role_code: str) -> int:
        result = await self._session.execute(
            select(Role.rank).where(Role.code == role_code)
        )
        rank = result.scalar_one_or_none()
        return rank if rank is not None else 0

    async def _load_target(
        self, membership_id: uuid.UUID, account_id: uuid.UUID
    ) -> Membership:
        membership = await self._members.get_by_id(membership_id)
        if membership is None or membership.account_id != account_id:
            raise MembershipNotFound()
        return membership

    async def _guard_rank(self, actor_role: str, target_role: str) -> None:
        """L'acteur ne peut pas agir sur un membre de rang supérieur au sien."""
        if await self._role_rank(target_role) > await self._role_rank(actor_role):
            raise RankTooHigh()

    async def _guard_not_last_owner(self, membership: Membership) -> None:
        """Empêche de retirer/rétrograder/suspendre le dernier OWNER actif."""
        if membership.role_code == "OWNER" and membership.status == "active":
            if await self._members.count_active_owners(membership.account_id) <= 1:
                raise LastOwner()

    async def change_role(
        self,
        account_id: uuid.UUID,
        membership_id: uuid.UUID,
        new_role: str,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> Membership:
        membership = await self._load_target(membership_id, account_id)
        await self._guard_rank(actor_role, membership.role_code)
        # On ne peut pas attribuer un rôle supérieur au sien.
        if await self._role_rank(new_role) > await self._role_rank(actor_role):
            raise RankTooHigh()
        if membership.role_code == "OWNER" and new_role != "OWNER":
            await self._guard_not_last_owner(membership)

        old = membership.role_code
        membership.role_code = new_role
        self._audit.add(
            actor_id,
            account_id,
            "member.role_changed",
            {"membership_id": str(membership_id), "from": old, "to": new_role},
        )
        await self._session.commit()
        await self._session.refresh(membership)
        return membership

    async def set_status(
        self,
        account_id: uuid.UUID,
        membership_id: uuid.UUID,
        new_status: str,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> Membership:
        membership = await self._load_target(membership_id, account_id)
        await self._guard_rank(actor_role, membership.role_code)
        if new_status != "active":
            await self._guard_not_last_owner(membership)

        membership.status = new_status
        self._audit.add(
            actor_id,
            account_id,
            "member.status_changed",
            {"membership_id": str(membership_id), "status": new_status},
        )
        await self._session.commit()
        await self._session.refresh(membership)
        return membership

    async def revoke(
        self,
        account_id: uuid.UUID,
        membership_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> None:
        membership = await self._load_target(membership_id, account_id)
        await self._guard_rank(actor_role, membership.role_code)
        await self._guard_not_last_owner(membership)

        membership.status = "revoked"
        self._audit.add(
            actor_id,
            account_id,
            "member.revoked",
            {"membership_id": str(membership_id)},
        )
        await self._session.commit()

    async def leave(self, account_id: uuid.UUID, identity_id: uuid.UUID) -> None:
        """Une identité révoque sa **propre** adhésion (ex. un coach quitte).

        Pas de garde de rang (on agit sur soi-même), mais garde-fou « dernier
        OWNER » : un client ne peut pas quitter/orpheliner son propre compte.
        """
        membership = await self._members.get_active(identity_id, account_id)
        if membership is None:
            raise MembershipNotFound()
        await self._guard_not_last_owner(membership)

        membership.status = "revoked"
        self._audit.add(
            identity_id,
            account_id,
            "member.left",
            {"membership_id": str(membership.id)},
        )
        await self._session.commit()
