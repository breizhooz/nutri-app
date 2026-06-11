"""Tests for the multi-account admin layer (invitations / members / audit)."""

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
    """Forge a context token (act_account + scopes of the role)."""
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


async def _make_user(session: AsyncSession, email: str) -> User:
    user = User(id=uuid.uuid4(), email=email, hashed_password=hash_password("x"))
    session.add(user)
    await session.flush()
    return user


async def _setup_account(
    session: AsyncSession, owner_email: str = "owner@test.com"
) -> tuple[User, Account, Membership]:
    """Seed roles + an account owned by a fresh OWNER user."""
    await seed_access(session)
    owner = await _make_user(session, owner_email)
    account = Account(name=owner_email, type="personal", created_by=owner.id)
    session.add(account)
    await session.flush()
    membership = Membership(
        identity_id=owner.id,
        account_id=account.id,
        role_code="OWNER",
        status="active",
    )
    session.add(membership)
    owner.default_account_id = account.id
    await session.commit()
    return owner, account, membership


# --- invitations ------------------------------------------------------------


@pytest.mark.unit
async def test_invite_creates_pending_invitation(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    token = _ctx_token(owner.id, account.id, "OWNER")
    resp = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "invitee@test.com", "role": "EDITOR"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["email"] == "invitee@test.com"
    assert body["token"]


@pytest.mark.unit
async def test_invite_rank_guard_blocks_higher_role(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un ADMIN ne peut pas inviter au rôle OWNER (rang supérieur)."""
    owner, account, _ = await _setup_account(db_session)
    admin = await _make_user(db_session, "admin@test.com")
    db_session.add(
        Membership(
            identity_id=admin.id,
            account_id=account.id,
            role_code="ADMIN",
            status="active",
        )
    )
    await db_session.commit()
    token = _ctx_token(admin.id, account.id, "ADMIN")
    resp = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "x@test.com", "role": "OWNER"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


@pytest.mark.unit
async def test_accept_invitation_creates_membership(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    invitee = await _make_user(db_session, "invitee@test.com")
    await db_session.commit()

    owner_token = _ctx_token(owner.id, account.id, "OWNER")
    inv = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "invitee@test.com", "role": "EDITOR"},
        headers=_auth(owner_token),
    )
    token = inv.json()["token"]

    resp = await anon_client.post(
        f"/api/v1/accounts/invitations/{token}/accept",
        headers=_auth(_plain_token(invitee.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "EDITOR"

    membership = (
        await db_session.execute(
            select(Membership).where(
                Membership.identity_id == invitee.id,
                Membership.account_id == account.id,
            )
        )
    ).scalar_one()
    assert membership.role_code == "EDITOR"
    assert membership.status == "active"


@pytest.mark.unit
async def test_accept_email_mismatch_forbidden(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    other = await _make_user(db_session, "other@test.com")
    await db_session.commit()
    owner_token = _ctx_token(owner.id, account.id, "OWNER")
    inv = await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "invitee@test.com", "role": "EDITOR"},
        headers=_auth(owner_token),
    )
    resp = await anon_client.post(
        f"/api/v1/accounts/invitations/{inv.json()['token']}/accept",
        headers=_auth(_plain_token(other.id)),
    )
    assert resp.status_code == 403


@pytest.mark.unit
async def test_accept_unknown_token_404(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    resp = await anon_client.post(
        "/api/v1/accounts/invitations/does-not-exist/accept",
        headers=_auth(_plain_token(owner.id)),
    )
    assert resp.status_code == 404


# --- members ----------------------------------------------------------------


@pytest.mark.unit
async def test_list_members(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    token = _ctx_token(owner.id, account.id, "OWNER")
    resp = await anon_client.get(
        f"/api/v1/accounts/{account.id}/members", headers=_auth(token)
    )
    assert resp.status_code == 200
    members = resp.json()["members"]
    assert len(members) == 1
    assert members[0]["role"] == "OWNER"


@pytest.mark.unit
async def test_revoke_last_owner_blocked(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, membership = await _setup_account(db_session)
    token = _ctx_token(owner.id, account.id, "OWNER")
    resp = await anon_client.delete(
        f"/api/v1/accounts/{account.id}/members/{membership.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 409


@pytest.mark.unit
async def test_change_role_then_revoke_member(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    member_user = await _make_user(db_session, "m@test.com")
    member = Membership(
        identity_id=member_user.id,
        account_id=account.id,
        role_code="EDITOR",
        status="active",
    )
    db_session.add(member)
    await db_session.commit()
    token = _ctx_token(owner.id, account.id, "OWNER")

    patch = await anon_client.patch(
        f"/api/v1/accounts/{account.id}/members/{member.id}",
        json={"role": "VIEWER"},
        headers=_auth(token),
    )
    assert patch.status_code == 200
    assert patch.json()["role"] == "VIEWER"

    rev = await anon_client.delete(
        f"/api/v1/accounts/{account.id}/members/{member.id}",
        headers=_auth(token),
    )
    assert rev.status_code == 204


# --- guard ------------------------------------------------------------------


@pytest.mark.unit
async def test_manage_forbidden_without_scope(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un EDITOR (sans member:manage) ne peut pas gérer les membres."""
    owner, account, _ = await _setup_account(db_session)
    editor = await _make_user(db_session, "editor@test.com")
    await db_session.commit()
    token = _ctx_token(editor.id, account.id, "EDITOR")
    resp = await anon_client.get(
        f"/api/v1/accounts/{account.id}/members", headers=_auth(token)
    )
    assert resp.status_code == 403


@pytest.mark.unit
async def test_manage_forbidden_when_acting_on_other_account(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """member:manage mais act_account != compte du chemin → 403."""
    owner, account, _ = await _setup_account(db_session)
    foreign = uuid.uuid4()
    token = _ctx_token(owner.id, foreign, "OWNER")
    resp = await anon_client.get(
        f"/api/v1/accounts/{account.id}/members", headers=_auth(token)
    )
    assert resp.status_code == 403


# --- audit ------------------------------------------------------------------


@pytest.mark.unit
async def test_invite_writes_audit(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, account, _ = await _setup_account(db_session)
    token = _ctx_token(owner.id, account.id, "OWNER")
    await anon_client.post(
        f"/api/v1/accounts/{account.id}/invitations",
        json={"email": "a@test.com", "role": "VIEWER"},
        headers=_auth(token),
    )
    resp = await anon_client.get(
        f"/api/v1/accounts/{account.id}/audit", headers=_auth(token)
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()["entries"]]
    assert "invitation.created" in actions
