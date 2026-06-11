"""Tests for the multi-account access layer (RBAC engine + endpoints)."""

import uuid

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_catalog import seed_access
from app.core.security import hash_password
from app.models.access import Account, Membership, MembershipScopeOverride
from app.models.user import User
from app.services.access_service import AccessService

# Mirrors conftest.TEST_USER_ID embedded in the auth_client bearer token.
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_JWT_SECRET = "test-secret-key-for-testing-only"


async def _seed_user_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    email: str = "owner@test.com",
    password: str = "password123",
    role: str = "OWNER",
) -> tuple[User, Account, Membership]:
    """Seed the catalogue + 1 user with a default account and a membership."""
    await seed_access(session)
    user = User(
        id=user_id or uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
    )
    session.add(user)
    await session.flush()
    account = Account(name=email, type="personal", created_by=user.id)
    session.add(account)
    await session.flush()
    membership = Membership(
        identity_id=user.id,
        account_id=account.id,
        role_code=role,
        status="active",
    )
    session.add(membership)
    user.default_account_id = account.id
    await session.commit()
    return user, account, membership


def _membership(role: str, *, status: str = "active", overrides=None) -> Membership:
    """Build a transient membership with its overrides set in memory.

    Setting ``overrides`` explicitly avoids an async lazy-load when
    ``effective_scopes`` iterates them.
    """
    m = Membership(
        identity_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        role_code=role,
        status=status,
    )
    m.overrides = overrides or []
    return m


# --- effective_scopes -------------------------------------------------------


@pytest.mark.unit
async def test_owner_gets_all_scopes(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    scopes = await svc.effective_scopes(_membership("OWNER"))
    assert "account:delete" in scopes
    assert len(scopes) == 10


@pytest.mark.unit
async def test_viewer_is_read_only(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    scopes = await svc.effective_scopes(_membership("VIEWER"))
    assert scopes == {"recipe:read", "plan:read", "profile:read", "journal:read"}
    assert not any(s.endswith(":write") for s in scopes)


@pytest.mark.unit
async def test_deny_override_removes_a_role_scope(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    membership = _membership(
        "EDITOR",
        overrides=[MembershipScopeOverride(scope_code="recipe:write", effect="deny")],
    )
    scopes = await svc.effective_scopes(membership)
    assert "recipe:write" not in scopes
    assert "recipe:read" in scopes


@pytest.mark.unit
async def test_grant_override_adds_a_scope(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    membership = _membership(
        "VIEWER",
        overrides=[MembershipScopeOverride(scope_code="journal:write", effect="grant")],
    )
    scopes = await svc.effective_scopes(membership)
    assert "journal:write" in scopes


@pytest.mark.unit
async def test_deny_beats_grant_on_same_scope(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    membership = _membership(
        "VIEWER",
        overrides=[
            MembershipScopeOverride(scope_code="recipe:write", effect="grant"),
            MembershipScopeOverride(scope_code="recipe:write", effect="deny"),
        ],
    )
    scopes = await svc.effective_scopes(membership)
    assert "recipe:write" not in scopes


@pytest.mark.unit
async def test_inactive_membership_grants_nothing(db_session: AsyncSession) -> None:
    await seed_access(db_session)
    svc = AccessService(db_session)
    scopes = await svc.effective_scopes(_membership("OWNER", status="revoked"))
    assert scopes == set()


# --- GET /accounts ----------------------------------------------------------


@pytest.mark.unit
async def test_list_accounts_returns_owner_account(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, account, _ = await _seed_user_account(
        db_session, user_id=TEST_USER_ID, email="me@test.com"
    )
    resp = await auth_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["accounts"]) == 1
    entry = data["accounts"][0]
    assert entry["id"] == str(account.id)
    assert entry["role"] == "OWNER"
    assert entry["is_default"] is True


# --- POST /accounts/{id}/switch ---------------------------------------------


@pytest.mark.unit
async def test_switch_to_own_account_returns_context_token(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, account, _ = await _seed_user_account(db_session, user_id=TEST_USER_ID)
    resp = await auth_client.post(f"/api/v1/accounts/{account.id}/switch")
    assert resp.status_code == 200
    payload = jwt.decode(
        resp.json()["access_token"], _JWT_SECRET, algorithms=["HS256"]
    )
    assert payload["sub"] == str(TEST_USER_ID)
    assert payload["act_account"] == str(account.id)
    assert payload["role"] == "OWNER"
    assert "recipe:write" in payload["scopes"]


@pytest.mark.unit
async def test_switch_to_foreign_account_returns_403(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user_account(db_session, user_id=TEST_USER_ID)
    foreign = Account(name="foreign", type="personal")
    db_session.add(foreign)
    await db_session.commit()
    resp = await auth_client.post(f"/api/v1/accounts/{foreign.id}/switch")
    assert resp.status_code == 403


# --- provisioning au signup -------------------------------------------------


@pytest.mark.unit
async def test_signup_provisions_personal_account(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un nouvel inscrit reçoit un compte personnel + membership OWNER."""
    resp = await anon_client.post(
        "/api/v1/users",
        json={"email": "fresh@test.com", "password": "password123"},
    )
    assert resp.status_code == 201
    user_id = uuid.UUID(resp.json()["id"])

    user = await db_session.get(User, user_id)
    assert user is not None
    assert user.default_account_id is not None

    membership = (
        await db_session.execute(
            select(Membership).where(Membership.identity_id == user_id)
        )
    ).scalar_one()
    assert membership.role_code == "OWNER"
    assert membership.status == "active"
    assert membership.account_id == user.default_account_id


# --- login enrichment (non-regression) --------------------------------------


@pytest.mark.unit
async def test_login_token_carries_account_context_and_keeps_rbac_claims(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user_account(
        db_session, email="ctx@test.com", password="password123"
    )
    resp = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "ctx@test.com", "password": "password123"},
    )
    assert resp.status_code == 200
    payload = jwt.decode(
        resp.json()["access_token"], _JWT_SECRET, algorithms=["HS256"]
    )
    # New context dimension...
    assert payload["role"] == "OWNER"
    assert "act_account" in payload
    assert "recipe:write" in payload["scopes"]
    # ...without dropping the identity-level claims the metier services read.
    assert "user_admin" in payload
    assert "user_right" in payload
