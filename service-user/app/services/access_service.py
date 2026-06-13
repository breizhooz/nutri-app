"""Business logic for the multi-account access layer (RBAC engine).

Computes effective scopes from a membership (role scopes adjusted by per-
membership overrides) and assembles the context claims embedded in the JWT so
downstream services know *in which account* the identity is acting and *with
which scopes*.
"""

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Account, Membership
from app.models.user import User
from app.repositories.access_repository import (
    MembershipRepository,
    RoleScopeRepository,
)
from app.services.user_service import UserService


class AccessService:
    """Service holding the RBAC logic (effective scopes, context claims)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._memberships = MembershipRepository(session)
        self._role_scopes = RoleScopeRepository(session)

    async def provision_personal_account(self, user: User) -> Account:
        """Create the personal account + OWNER membership for a new identity.

        Guarantees the invariant "every identity has a default account": creates
        an ``Account`` owned by the user, an active OWNER ``Membership``, and sets
        ``user.default_account_id``. Idempotent-friendly: if the user already has
        a default account, it is returned untouched.

        Does not commit — the caller owns the transaction (so account creation is
        atomic with the user insert).
        """
        if user.default_account_id is not None:
            existing = await self._session.get(Account, user.default_account_id)
            if existing is not None:
                return existing

        account = Account(name=user.email, type="personal", created_by=user.id)
        self._session.add(account)
        await self._session.flush()  # assign account.id

        self._session.add(
            Membership(
                identity_id=user.id,
                account_id=account.id,
                role_code="OWNER",
                status="active",
            )
        )
        user.default_account_id = account.id
        await self._session.flush()
        return account

    async def effective_scopes(self, membership: Membership) -> set[str]:
        """Compute the scopes effectively granted by a membership.

        ``effective = (role scopes ∪ grant overrides) − deny overrides``.
        ``deny`` always wins. A non-active membership grants nothing.
        """
        if membership.status != "active":
            return set()
        base = await self._role_scopes.scopes_for_role(membership.role_code)
        grants = {o.scope_code for o in membership.overrides if o.effect == "grant"}
        denies = {o.scope_code for o in membership.overrides if o.effect == "deny"}
        return (base | grants) - denies

    async def get_active_membership(
        self, identity_id: uuid.UUID, account_id: uuid.UUID
    ) -> Optional[Membership]:
        """Return the active membership linking an identity to an account."""
        return await self._memberships.get_active(identity_id, account_id)

    async def list_accessible_accounts(
        self, identity_id: uuid.UUID
    ) -> list[tuple[Account, str]]:
        """Return ``(account, role_code)`` pairs the identity can access."""
        rows = await self._memberships.list_for_identity(identity_id)
        return [(account, membership.role_code) for membership, account in rows]

    async def build_context_claims(
        self, user: User, membership: Membership, scopes: set[str]
    ) -> dict[str, Any]:
        """Assemble the JWT claims for a context (account-scoped) token.

        Identity-level claims (``user_admin``/``user_right``) are reused from
        :meth:`UserService.build_token_claims` so they are never duplicated; the
        account dimension (``act_account``/``role``/``scopes``) comes from the
        membership.
        """
        return {
            **UserService.build_token_claims(user),
            "act_account": str(membership.account_id),
            "role": membership.role_code,
            "scopes": sorted(scopes),
        }

    async def build_login_claims(self, user: User) -> dict[str, Any]:
        """Build the claims for the token issued at login/refresh/oauth.

        If the user has a default account with an active membership, the token
        is context-ready (carries ``act_account``/``role``/``scopes``). Falls
        back gracefully to the bare identity claims otherwise, so authentication
        never breaks because of an access-layer hiccup. Always carries
        ``health_consent`` (RGPD art. 9) so service-profile peut autoriser ou
        refuser localement le traitement des données de santé.
        """
        claims = await self._base_login_claims(user)
        # Import différé : évite un cycle access_service ↔ consent_service éventuel.
        from app.services.consent_service import ConsentService

        claims["health_consent"] = await ConsentService(
            self._session
        ).has_active_health_consent(user.id)
        return claims

    async def _base_login_claims(self, user: User) -> dict[str, Any]:
        """Claims RBAC (contexte de compte si dispo, sinon identité nue)."""
        if user.default_account_id is None:
            return UserService.build_token_claims(user)
        membership = await self.get_active_membership(
            user.id, user.default_account_id
        )
        if membership is None:
            return UserService.build_token_claims(user)
        scopes = await self.effective_scopes(membership)
        return await self.build_context_claims(user, membership, scopes)
