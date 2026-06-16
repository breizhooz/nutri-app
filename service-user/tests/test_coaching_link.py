"""Tests for the coach→client link (coaching model, docs/coaching_model.md).

Couvre l'inversion de l'invitation (`kind='coach_link'`) : à l'acceptation, c'est
le COACH (inviteur) qui est greffé sur le compte du CLIENT (accepteur), avec les
garde-fous (1 coach actif, pas de self-coaching, ré-établissement, self-leave).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_catalog import ROLE_SCOPES, seed_access
from app.core.security import hash_password
from app.models.access import Account, Membership
from app.models.user import User

_JWT_SECRET = "test-secret-key-for-testing-only"


def _ctx_token(sub: uuid.UUID, account_id: uuid.UUID, role: str) -> str:
    payload = {
        "sub": str(sub),
        "type": "access",
        "act_account": str(account_id),
        "role": role,
        "scopes": sorted(ROLE_SCOPES[role]),
        "user_admin": False,
        "user_right": {},
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _plain_token(sub: uuid.UUID) -> str:
    payload = {
        "sub": str(sub),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_account(
    session: AsyncSession, email: str, *, is_coach: bool = False
) -> tuple[User, Account]:
    """Seed roles + a user OWNER of their own personal account.

    ``is_coach`` accorde la capacité identité « coach » (sinon le backend refuse
    la création d'un lien coach_link).
    """
    await seed_access(session)
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password("x"),
        is_coach=is_coach,
    )
    session.add(user)
    await session.flush()
    account = Account(name=email, type="personal", created_by=user.id)
    session.add(account)
    await session.flush()
    session.add(
        Membership(
            identity_id=user.id,
            account_id=account.id,
            role_code="OWNER",
            status="active",
        )
    )
    user.default_account_id = account.id
    await session.commit()
    return user, account


async def _invite_coach_link(
    client: AsyncClient, coach: User, coach_account: Account, client_email: str
) -> str:
    """Coach envoie une invitation coach_link depuis son compte → renvoie le token."""
    resp = await client.post(
        f"/api/v1/accounts/{coach_account.id}/invitations",
        json={"email": client_email, "role": "VIEWER", "kind": "coach_link"},
        headers=_auth(_ctx_token(coach.id, coach_account.id, "OWNER")),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _active_coach(session: AsyncSession, account_id: uuid.UUID):
    return (
        await session.execute(
            select(Membership).where(
                Membership.account_id == account_id,
                Membership.role_code == "COACH",
                Membership.status == "active",
            )
        )
    ).scalar_one_or_none()


# --- invitation ------------------------------------------------------------


@pytest.mark.unit
async def test_coach_link_invite_forces_coach_role(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """kind=coach_link : le rôle est imposé à COACH quel que soit le champ role."""
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    resp = await anon_client.post(
        f"/api/v1/accounts/{coach_acc.id}/invitations",
        json={"email": "client@test.com", "role": "VIEWER", "kind": "coach_link"},
        headers=_auth(_ctx_token(coach.id, coach_acc.id, "OWNER")),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "coach_link"
    assert body["role"] == "COACH"


# --- inversion de l'acceptation --------------------------------------------


@pytest.mark.unit
async def test_accept_coach_link_grafts_coach_on_client_account(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    client_user, client_acc = await _setup_account(db_session, "client@test.com")

    token = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    resp = await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert resp.status_code == 200, resp.text
    # La réponse décrit le compte du client, vu par le client (OWNER), pas COACH.
    assert resp.json()["role"] == "OWNER"
    assert resp.json()["id"] == str(client_acc.id)

    # Le coach a une adhésion COACH active sur le compte DU CLIENT.
    coach_m = (
        await db_session.execute(
            select(Membership).where(
                Membership.identity_id == coach.id,
                Membership.account_id == client_acc.id,
            )
        )
    ).scalar_one()
    assert coach_m.role_code == "COACH"
    assert coach_m.status == "active"

    # Aucune adhésion du client sur le compte du coach (pas d'inversion subie).
    leaked = (
        await db_session.execute(
            select(Membership).where(
                Membership.identity_id == client_user.id,
                Membership.account_id == coach_acc.id,
            )
        )
    ).scalar_one_or_none()
    assert leaked is None


@pytest.mark.unit
async def test_coach_can_switch_into_client_account_with_coach_scopes(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    client_user, client_acc = await _setup_account(db_session, "client@test.com")
    token = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    # Le coach voit le compte client et peut basculer dessus.
    resp = await anon_client.post(
        f"/api/v1/accounts/{client_acc.id}/switch",
        headers=_auth(_plain_token(coach.id)),
    )
    assert resp.status_code == 200, resp.text
    claims = jwt.decode(resp.json()["access_token"], _JWT_SECRET, algorithms=["HS256"])
    assert claims["act_account"] == str(client_acc.id)
    assert claims["role"] == "COACH"
    assert "profile:write" in claims["scopes"]
    assert "journal:write" not in claims["scopes"]


# --- garde-fous ------------------------------------------------------------


@pytest.mark.unit
async def test_single_coach_per_client(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach1, acc1 = await _setup_account(db_session, "coach1@test.com", is_coach=True)
    coach2, acc2 = await _setup_account(db_session, "coach2@test.com", is_coach=True)
    client_user, _ = await _setup_account(db_session, "client@test.com")

    t1 = await _invite_coach_link(anon_client, coach1, acc1, "client@test.com")
    r1 = await anon_client.post(
        f"/api/v1/accounts/invitations/{t1}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert r1.status_code == 200

    t2 = await _invite_coach_link(anon_client, coach2, acc2, "client@test.com")
    r2 = await anon_client.post(
        f"/api/v1/accounts/invitations/{t2}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert r2.status_code == 409


@pytest.mark.unit
async def test_cannot_coach_self(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    token = await _invite_coach_link(anon_client, coach, coach_acc, "coach@test.com")
    resp = await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(coach.id)),
    )
    assert resp.status_code == 400


# --- self-leave & ré-établissement -----------------------------------------


@pytest.mark.unit
async def test_coach_leaves_then_link_reestablished(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    client_user, client_acc = await _setup_account(db_session, "client@test.com")

    t1 = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    await anon_client.post(
        f"/api/v1/accounts/invitations/{t1}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )

    # Le coach coupe le lien (self-leave) — pas besoin de member:manage.
    left = await anon_client.delete(
        f"/api/v1/accounts/{client_acc.id}/membership/me",
        headers=_auth(_plain_token(coach.id)),
    )
    assert left.status_code == 204
    assert await _active_coach(db_session, client_acc.id) is None

    # Ré-établissement : nouvelle invitation + acceptation → adhésion réactivée.
    t2 = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    r2 = await anon_client.post(
        f"/api/v1/accounts/invitations/{t2}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert r2.status_code == 200
    reactivated = await _active_coach(db_session, client_acc.id)
    assert reactivated is not None
    assert reactivated.identity_id == coach.id
    # Toujours une seule ligne (identity, account) : on a réactivé, pas dupliqué.
    rows = (
        (
            await db_session.execute(
                select(Membership).where(
                    Membership.identity_id == coach.id,
                    Membership.account_id == client_acc.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.unit
async def test_client_cannot_leave_own_account_last_owner(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    client_user, client_acc = await _setup_account(db_session, "client@test.com")
    resp = await anon_client.delete(
        f"/api/v1/accounts/{client_acc.id}/membership/me",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert resp.status_code == 409


# --- capacité coach + côté client ------------------------------------------


@pytest.mark.unit
async def test_non_coach_cannot_create_coach_link(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sans la capacité is_coach, créer un lien coach_link est refusé (403)."""
    owner, account = await _setup_account(
        db_session, "owner@test.com"
    )  # is_coach False
    resp = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "client@test.com", "role": "VIEWER", "kind": "coach_link"},
        headers=_auth(_ctx_token(owner.id, account.id, "OWNER")),
    )
    assert resp.status_code == 403


@pytest.mark.unit
async def test_client_sees_and_revokes_own_coach(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    client_user, client_acc = await _setup_account(db_session, "client@test.com")
    token = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )

    # Le client voit son coach.
    seen = await anon_client.get(
        f"/api/v1/accounts/{client_acc.id}/coach",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert seen.status_code == 200
    assert seen.json()["email"] == "coach@test.com"

    # Le client coupe le lien (seule action permise).
    cut = await anon_client.delete(
        f"/api/v1/accounts/{client_acc.id}/coach",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert cut.status_code == 204
    assert await _active_coach(db_session, client_acc.id) is None


@pytest.mark.unit
async def test_deleting_client_removes_account_and_coach_link(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Supprimer le client supprime son compte ET le lien coach (plus d'orphelin)."""
    from app.repositories.user_repository import UserRepository

    coach, coach_acc = await _setup_account(db_session, "coach@test.com", is_coach=True)
    client_user, client_acc = await _setup_account(db_session, "client@test.com")
    token = await _invite_coach_link(anon_client, coach, coach_acc, "client@test.com")
    await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(client_user.id)),
    )
    assert await _active_coach(db_session, client_acc.id) is not None

    await UserRepository(db_session).delete(client_user)

    assert await db_session.get(Account, client_acc.id) is None
    coach_m = (
        await db_session.execute(
            select(Membership).where(
                Membership.identity_id == coach.id,
                Membership.account_id == client_acc.id,
            )
        )
    ).scalar_one_or_none()
    assert coach_m is None


@pytest.mark.unit
async def test_outsider_cannot_read_account_coach(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Seul le propriétaire (ou un admin) peut consulter le coach d'un compte."""
    _client_user, client_acc = await _setup_account(db_session, "client@test.com")
    stranger, _ = await _setup_account(db_session, "stranger@test.com")
    resp = await anon_client.get(
        f"/api/v1/accounts/{client_acc.id}/coach",
        headers=_auth(_plain_token(stranger.id)),
    )
    assert resp.status_code == 403


# --- régression : le mode collaboratif est inchangé ------------------------


@pytest.mark.unit
async def test_collaborator_invite_still_joins_inviter_account(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account = await _setup_account(db_session, "owner@test.com")
    invitee = User(
        id=uuid.uuid4(), email="invitee@test.com", hashed_password=hash_password("x")
    )
    db_session.add(invitee)
    await db_session.commit()

    inv = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "invitee@test.com", "role": "EDITOR"},
        headers=_auth(_ctx_token(owner.id, account.id, "OWNER")),
    )
    assert inv.json()["kind"] == "collaborator"
    resp = await anon_client.post(
        f"/api/v1/accounts/invitations/{inv.json()['token']}/accept",
        headers=_auth(_plain_token(invitee.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "EDITOR"
    m = (
        await db_session.execute(
            select(Membership).where(
                Membership.identity_id == invitee.id,
                Membership.account_id == account.id,
            )
        )
    ).scalar_one()
    assert m.role_code == "EDITOR"
