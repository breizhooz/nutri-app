"""Business logic for account-share invitations (multi-account phase 3)."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.access import Account, Invitation, Membership, Role
from app.models.user import User
from app.repositories.access_repository import (
    AuditRepository,
    InvitationRepository,
    MembershipRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.access_errors import (
    AlreadyMember,
    CannotCoachSelf,
    CoachAlreadyAssigned,
    InvitationEmailMismatch,
    InvitationInvalid,
    InvitationNotFound,
    NoClientAccount,
    RankTooHigh,
)
from app.services.notification_client import NotificationClient

_INVITATION_TTL_DAYS = 7
# Rôle imposé pour un lien de coaching (le client ne choisit pas le rôle du coach).
_COACH_ROLE = "COACH"


class InvitationService:
    """Create / accept / cancel invitations to share an account."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._inv = InvitationRepository(session)
        self._members = MembershipRepository(session)
        self._audit = AuditRepository(session)
        self._users = UserRepository(session)

    async def _role_rank(self, role_code: str) -> int:
        result = await self._session.execute(
            select(Role.rank).where(Role.code == role_code)
        )
        rank = result.scalar_one_or_none()
        return rank if rank is not None else 0

    async def invite(
        self,
        account_id: uuid.UUID,
        inviter_id: uuid.UUID,
        inviter_role: str,
        email: str,
        role_code: str,
        kind: str = "collaborator",
    ) -> Invitation:
        """Create a pending invitation. Best-effort email; token returned for dev.

        ``kind='collaborator'`` : l'invité rejoindra ``account_id``.
        ``kind='coach_link'`` : l'acceptation donnera à l'inviteur (le coach) une
        délégation **sur le compte du client** (l'accepteur). Le rôle est alors
        imposé à ``COACH`` ; ``account_id`` n'est que le contexte d'origine.
        """
        if kind == "coach_link":
            # Le client ne choisit pas le rôle du coach : il est imposé.
            role_code = _COACH_ROLE
        elif kind != "collaborator":
            raise InvitationInvalid()

        # Rank guard : on ne peut pas inviter à un rôle supérieur au sien.
        if await self._role_rank(role_code) > await self._role_rank(inviter_role):
            raise RankTooHigh()

        invitation = Invitation(
            account_id=account_id,
            email=email.strip().lower(),
            role_code=role_code,
            kind=kind,
            token=secrets.token_urlsafe(32),
            status="pending",
            invited_by=inviter_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=_INVITATION_TTL_DAYS),
        )
        self._inv.add(invitation)
        self._audit.add(
            inviter_id,
            account_id,
            "coach_link.created" if kind == "coach_link" else "invitation.created",
            {"email": invitation.email, "role": role_code, "kind": kind},
        )
        await self._session.commit()
        await self._session.refresh(invitation)

        await self._send_email(invitation)
        return invitation

    async def _send_email(self, invitation: Invitation) -> None:
        if not settings.NOTIFICATION_SERVICE_URL:
            return
        account = await self._session.get(Account, invitation.account_id)
        accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={invitation.token}"
        await NotificationClient.send_invitation_email(
            recipient_email=invitation.email,
            account_name=account.name if account else "un dossier",
            role_code=invitation.role_code,
            accept_url=accept_url,
            notification_url=settings.NOTIFICATION_SERVICE_URL,
            notification_token=settings.NOTIFICATION_SERVICE_TOKEN,
        )

    async def accept(self, token: str, identity: User) -> Membership:
        """Accept an invitation as the matching identity → create the membership.

        Selon ``invitation.kind`` :
          - ``collaborator`` : ``identity`` (l'accepteur) rejoint le compte de
            l'inviteur (``invitation.account_id``) avec ``role_code``.
          - ``coach_link`` : l'accepteur est le **client** ; on greffe l'inviteur
            (le **coach**) comme ``COACH`` **sur le compte du client**. C'est
            l'inversion centrale du modèle coach→client.

        Dans les deux cas, l'email de l'accepteur doit correspondre à l'invitation.
        Retourne le ``Membership`` créé/réactivé.
        """
        invitation = await self._inv.get_by_token(token)
        if invitation is None or invitation.status != "pending":
            raise InvitationNotFound()

        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            invitation.status = "expired"
            await self._session.commit()
            raise InvitationInvalid()

        if invitation.email != (identity.email or "").strip().lower():
            raise InvitationEmailMismatch()

        if invitation.kind == "coach_link":
            membership = await self._accept_coach_link(invitation, identity)
        else:
            membership = await self._accept_collaborator(invitation, identity)

        invitation.status = "accepted"
        await self._session.commit()
        await self._session.refresh(membership)
        return membership

    async def _accept_collaborator(
        self, invitation: Invitation, identity: User
    ) -> Membership:
        """Socle : l'accepteur rejoint le compte de l'inviteur."""
        existing = await self._members.get_for_account(
            identity.id, invitation.account_id
        )
        if existing is not None:
            raise AlreadyMember()

        membership = Membership(
            identity_id=identity.id,
            account_id=invitation.account_id,
            role_code=invitation.role_code,
            status="active",
            invited_by=invitation.invited_by,
        )
        self._members.add(membership)
        self._audit.add(
            identity.id,
            invitation.account_id,
            "invitation.accepted",
            {"email": invitation.email, "role": invitation.role_code},
        )
        return membership

    async def _accept_coach_link(
        self, invitation: Invitation, identity: User
    ) -> Membership:
        """Coaching : le coach (inviteur) est greffé sur le compte du client.

        ``identity`` = le client qui accepte. La délégation vise SON compte par
        défaut. Garde-fou : un seul coach actif par compte client.
        """
        coach_id = invitation.invited_by
        if coach_id is None:
            raise InvitationInvalid()
        if coach_id == identity.id:
            raise CannotCoachSelf()

        client_account = identity.default_account_id
        if client_account is None:
            raise NoClientAccount()

        # Un seul coach actif par client.
        active_coach = await self._members.get_active_coach(client_account)
        if active_coach is not None:
            if active_coach.identity_id == coach_id:
                raise AlreadyMember()
            raise CoachAlreadyAssigned()

        # Ré-établissement : si ce coach a une adhésion antérieure (révoquée) sur
        # ce compte, on la réactive (contrainte d'unicité (identité, compte)).
        prior = await self._members.get_for_account(coach_id, client_account)
        if prior is not None:
            prior.role_code = _COACH_ROLE
            prior.status = "active"
            prior.revoked_at = None
            membership = prior
        else:
            membership = Membership(
                identity_id=coach_id,
                account_id=client_account,
                role_code=_COACH_ROLE,
                status="active",
                invited_by=coach_id,
            )
            self._members.add(membership)

        self._audit.add(
            identity.id,
            client_account,
            "coach_link.accepted",
            {"email": invitation.email, "coach": str(coach_id)},
        )
        return membership

    async def cancel(
        self,
        invitation_id: uuid.UUID,
        account_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """Revoke a pending invitation."""
        invitation = await self._inv.get_by_id(invitation_id)
        if (
            invitation is None
            or invitation.account_id != account_id
            or invitation.status != "pending"
        ):
            raise InvitationNotFound()
        invitation.status = "revoked"
        self._audit.add(
            actor_id,
            account_id,
            "invitation.cancelled",
            {"email": invitation.email},
        )
        await self._session.commit()

    async def list_pending(self, account_id: uuid.UUID) -> list[Invitation]:
        return await self._inv.list_pending_for_account(account_id)
