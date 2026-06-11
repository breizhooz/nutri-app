"""Multi-account routes: list accessible accounts and switch context.

The login is unique (one identity) but the UI works *inside* one account at a
time. ``GET /accounts`` lists the accounts the identity can access; the switch
endpoint re-issues a short context token scoped to the chosen account, rather
than packing every account's rights into a single token.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from nutri_shared.core.context import AccessContext

from app.core.deps import get_current_user, get_locale, require_account_manager
from app.core.security import create_access_token
from app.db.session import get_session
from app.i18n.loader import t
from app.models.access import Account
from app.models.user import User
from app.schemas.account import (
    AccountListResponse,
    AccountSummary,
    AuditEntry,
    AuditListResponse,
    CoachInfo,
    InvitationCreate,
    InvitationListResponse,
    InvitationPreview,
    InvitationResponse,
    MemberListResponse,
    MemberSummary,
    RoleChange,
)
from app.schemas.user import TokenResponse
from app.services.access_errors import AccountAccessError
from app.repositories.access_repository import (
    AuditRepository,
    InvitationRepository,
    MembershipRepository,
)
from app.services.access_service import AccessService
from app.services.invitation_service import InvitationService
from app.services.member_service import MemberService

router: APIRouter = APIRouter()


class AccessServiceFactory:
    """FastAPI dependency factory wiring :class:`AccessService`."""

    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> AccessService:
        return AccessService(session)


def _http_error(request: Request, exc: AccountAccessError) -> HTTPException:
    """Map a domain access error to a localized HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail=t.get(exc.detail_key, get_locale(request)),
    )


def _actor_role(ctx: AccessContext) -> str:
    """Rôle effectif de l'acteur pour les garde-fous de rang.

    Un platform_admin (SAV) agit au niveau OWNER (rang max) ; sinon = rôle du
    membership porté par le token de contexte.
    """
    return "OWNER" if ctx.user_admin else (ctx.role or "VIEWER")


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    current_user: User = Depends(get_current_user),
    service: AccessService = Depends(AccessServiceFactory.inject),
) -> AccountListResponse:
    """List every account the authenticated identity can access."""
    pairs = await service.list_accessible_accounts(current_user.id)
    return AccountListResponse(
        accounts=[
            AccountSummary(
                id=account.id,
                name=account.name,
                role=role_code,
                is_default=account.id == current_user.default_account_id,
            )
            for account, role_code in pairs
        ]
    )


@router.post("/{account_id}/switch", response_model=TokenResponse)
async def switch_account(
    request: Request,
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AccessService = Depends(AccessServiceFactory.inject),
) -> TokenResponse:
    """Issue a fresh access token scoped to ``account_id``.

    403 if the identity has no active membership on that account. The refresh
    cookie (tied to the identity) is intentionally not re-issued here.
    """
    membership = await service.get_active_membership(current_user.id, account_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("accounts.not_member", get_locale(request)),
        )
    scopes = await service.effective_scopes(membership)
    claims = await service.build_context_claims(current_user, membership, scopes)
    return TokenResponse(access_token=create_access_token(str(current_user.id), claims))


@router.get("/{account_id}/access/{identity_id}")
async def get_member_access(
    account_id: uuid.UUID,
    identity_id: uuid.UUID,
    service: AccessService = Depends(AccessServiceFactory.inject),
) -> dict[str, object]:
    """Rôle + scopes effectifs d'une identité sur un compte (endpoint interne).

    Utilisé par les services métier (ex. service-recipe pour le push de recettes
    d'un coach vers un client) afin de vérifier qu'une identité a bien un scope
    donné sur un compte qui n'est pas son compte actif. Renvoie ``{role: null,
    scopes: []}`` si aucune adhésion active.
    """
    membership = await service.get_active_membership(identity_id, account_id)
    if membership is None:
        return {"role": None, "scopes": []}
    scopes = await service.effective_scopes(membership)
    return {"role": membership.role_code, "scopes": sorted(scopes)}


async def _require_account_owner(
    request: Request,
    account_id: uuid.UUID,
    current_user: User,
    service: AccessService,
) -> None:
    """403 sauf si l'appelant est OWNER du compte (ou admin plateforme)."""
    if current_user.user_admin:
        return
    membership = await service.get_active_membership(current_user.id, account_id)
    if membership is None or membership.role_code != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("accounts.not_owner", get_locale(request)),
        )


@router.get("/{account_id}/coach", response_model=CoachInfo)
async def get_account_coach(
    request: Request,
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AccessService = Depends(AccessServiceFactory.inject),
    session: AsyncSession = Depends(get_session),
) -> CoachInfo:
    """Coach actif du compte (côté client : onglet « Mon coach » du profil)."""
    await _require_account_owner(request, account_id, current_user, service)
    coach = await MembershipRepository(session).get_active_coach(account_id)
    if coach is None:
        return CoachInfo()
    coach_user = await session.get(User, coach.identity_id)
    return CoachInfo(
        membership_id=coach.id,
        email=coach_user.email if coach_user else None,
    )


@router.delete("/{account_id}/coach", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_account_coach(
    request: Request,
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: AccessService = Depends(AccessServiceFactory.inject),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Le client (OWNER) coupe le lien avec son coach. Seule action permise au client."""
    await _require_account_owner(request, account_id, current_user, service)
    coach = await MembershipRepository(session).get_active_coach(account_id)
    if coach is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("accounts.membership_not_found", get_locale(request)),
        )
    try:
        await MemberService(session).revoke(
            account_id, coach.id, current_user.id, "OWNER"
        )
    except AccountAccessError as exc:
        raise _http_error(request, exc)


# ── Phase 3 : gestion des membres & invitations (scope member:manage) ─────────


@router.get("/{account_id}/members", response_model=MemberListResponse)
async def list_members(
    account_id: uuid.UUID,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> MemberListResponse:
    """Membres du compte (gestionnaires uniquement)."""
    rows = await MemberService(session).list_members(account_id)
    return MemberListResponse(
        members=[
            MemberSummary(
                membership_id=m.id,
                identity_id=m.identity_id,
                email=u.email,
                role=m.role_code,
                status=m.status,
            )
            for m, u in rows
        ]
    )


@router.post(
    "/{account_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    request: Request,
    account_id: uuid.UUID,
    data: InvitationCreate,
    ctx: AccessContext = Depends(require_account_manager),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InvitationResponse:
    """Invite un email à rejoindre le compte avec un rôle.

    Un lien de coaching (``kind='coach_link'``) est réservé aux **coachs**
    (capacité ``is_coach`` accordée par un admin) et aux admins plateforme.
    """
    if data.kind == "coach_link" and not (
        current_user.is_coach or current_user.user_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("accounts.coach_capability_required", get_locale(request)),
        )
    try:
        inv = await InvitationService(session).invite(
            account_id=account_id,
            inviter_id=uuid.UUID(ctx.sub),
            inviter_role=_actor_role(ctx),
            email=str(data.email),
            role_code=data.role,
            kind=data.kind,
        )
    except AccountAccessError as exc:
        raise _http_error(request, exc)
    return InvitationResponse(
        id=inv.id,
        account_id=inv.account_id,
        email=inv.email,
        role=inv.role_code,
        status=inv.status,
        kind=inv.kind,
        token=inv.token,
        expires_at=inv.expires_at,
    )


@router.get("/{account_id}/invitations", response_model=InvitationListResponse)
async def list_invitations(
    account_id: uuid.UUID,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> InvitationListResponse:
    invs = await InvitationService(session).list_pending(account_id)
    return InvitationListResponse(
        invitations=[
            InvitationResponse(
                id=i.id,
                account_id=i.account_id,
                email=i.email,
                role=i.role_code,
                status=i.status,
                kind=i.kind,
                token=i.token,
                expires_at=i.expires_at,
            )
            for i in invs
        ]
    )


@router.delete(
    "/{account_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_invitation(
    request: Request,
    account_id: uuid.UUID,
    invitation_id: uuid.UUID,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await InvitationService(session).cancel(
            invitation_id, account_id, uuid.UUID(ctx.sub)
        )
    except AccountAccessError as exc:
        raise _http_error(request, exc)


@router.patch("/{account_id}/members/{membership_id}", response_model=MemberSummary)
async def update_member(
    request: Request,
    account_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: RoleChange,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> MemberSummary:
    """Change le rôle et/ou le statut (suspend/reactivate) d'un membre."""
    svc = MemberService(session)
    actor_id = uuid.UUID(ctx.sub)
    actor_role = _actor_role(ctx)
    try:
        membership = None
        if data.role is not None:
            membership = await svc.change_role(
                account_id, membership_id, data.role, actor_id, actor_role
            )
        if data.status is not None:
            membership = await svc.set_status(
                account_id, membership_id, data.status, actor_id, actor_role
            )
    except AccountAccessError as exc:
        raise _http_error(request, exc)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("accounts.nothing_to_update", get_locale(request)),
        )
    # Recharge l'email pour la réponse.
    rows = await svc.list_members(account_id)
    email = next((u.email for m, u in rows if m.id == membership.id), "")
    return MemberSummary(
        membership_id=membership.id,
        identity_id=membership.identity_id,
        email=email,
        role=membership.role_code,
        status=membership.status,
    )


@router.delete(
    "/{account_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_member(
    request: Request,
    account_id: uuid.UUID,
    membership_id: uuid.UUID,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await MemberService(session).revoke(
            account_id, membership_id, uuid.UUID(ctx.sub), _actor_role(ctx)
        )
    except AccountAccessError as exc:
        raise _http_error(request, exc)


@router.get("/{account_id}/audit", response_model=AuditListResponse)
async def list_audit(
    account_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    ctx: AccessContext = Depends(require_account_manager),
    session: AsyncSession = Depends(get_session),
) -> AuditListResponse:
    entries = await AuditRepository(session).list_for_account(
        account_id, limit=min(limit, 200), offset=offset
    )
    return AuditListResponse(
        entries=[
            AuditEntry(
                id=e.id,
                actor_identity_id=e.actor_identity_id,
                action=e.action,
                payload=e.payload,
                created_at=e.created_at,
            )
            for e in entries
        ]
    )


@router.get("/invitations/{token}/preview", response_model=InvitationPreview)
async def preview_invitation(
    request: Request,
    token: str,
    session: AsyncSession = Depends(get_session),
) -> InvitationPreview:
    """Aperçu public d'une invitation (avant acceptation) pour le consentement.

    Permet au front d'afficher un écran adapté (« X veut devenir votre coach »
    pour un coach_link) avant que la personne n'accepte. Pas d'auth : le token
    long fait foi.
    """
    inv = await InvitationRepository(session).get_by_token(token)
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("accounts.invitation_not_found", get_locale(request)),
        )
    account = await session.get(Account, inv.account_id)
    inviter = await session.get(User, inv.invited_by) if inv.invited_by else None
    return InvitationPreview(
        email=inv.email,
        role=inv.role_code,
        kind=inv.kind,
        status=inv.status,
        account_name=account.name if account else "",
        inviter_email=inviter.email if inviter else None,
    )


@router.post("/invitations/{token}/accept", response_model=AccountSummary)
async def accept_invitation(
    request: Request,
    token: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccountSummary:
    """Accepte une invitation.

    - collaborator : l'appelant rejoint le compte de l'inviteur.
    - coach_link : l'appelant (client) accorde au coach un accès à SON compte ; la
      réponse décrit alors le compte du client **vu par le client** (rôle OWNER),
      pas le membership du coach qui vient d'être créé.
    """
    svc = InvitationService(session)
    try:
        membership = await svc.accept(token, current_user)
    except AccountAccessError as exc:
        raise _http_error(request, exc)
    account = await session.get(Account, membership.account_id)
    # Rôle de l'appelant sur ce compte (pour coach_link, le membership renvoyé est
    # celui du coach → on récupère le rôle propre de l'appelant, OWNER de son compte).
    own = await AccessService(session).get_active_membership(
        current_user.id, membership.account_id
    )
    return AccountSummary(
        id=membership.account_id,
        name=account.name if account else "",
        role=own.role_code if own else membership.role_code,
        is_default=membership.account_id == current_user.default_account_id,
    )


@router.delete(
    "/{account_id}/membership/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_account(
    request: Request,
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Quitte un compte dont on est membre (ex. un coach « coupe le lien »).

    Ne requiert pas ``member:manage`` (un coach n'a pas ce scope) : chacun peut
    révoquer sa **propre** adhésion. Garde-fou : on ne peut pas quitter si on est
    le dernier OWNER (un client n'orpheline pas son compte).
    """
    try:
        await MemberService(session).leave(account_id, current_user.id)
    except AccountAccessError as exc:
        raise _http_error(request, exc)
