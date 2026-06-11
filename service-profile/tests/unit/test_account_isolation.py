"""Tests de la frontière de compte : isolation par account_id + enforcement scope.

Contrairement au fixture ``client`` (qui injecte un contexte via overrides), ces
tests utilisent ``raw_client`` (auth réelle) + des JWT forgés, pour exercer le
vrai ``require_scope`` et la résolution par ``act_account``.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from tests.conftest import make_context_token

_RW = ["profile:read", "profile:write"]


async def _insert_profile(
    session: AsyncSession,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    weight: float,
) -> Profile:
    profile = Profile(
        account_id=account_id,
        user_id=user_id,
        slug=f"profile-{uuid.uuid4().hex[:12]}",
        weight_kg=weight,
    )
    session.add(profile)
    await session.commit()
    return profile


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.unit
async def test_me_resolves_only_active_account(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """GET /me renvoie le dossier du compte actif, pas celui d'un autre compte."""
    acc_a, acc_b = uuid.uuid4(), uuid.uuid4()
    await _insert_profile(session, acc_a, uuid.uuid4(), weight=70.0)
    await _insert_profile(session, acc_b, uuid.uuid4(), weight=99.0)

    token = make_context_token(sub=uuid.uuid4(), account_id=acc_a, scopes=_RW)
    resp = await raw_client.get("/api/v1/profiles/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == pytest.approx(70.0, abs=0.01)


@pytest.mark.unit
async def test_account_without_dossier_is_isolated(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """Un compte sans dossier obtient 404 même si d'autres dossiers existent."""
    await _insert_profile(session, uuid.uuid4(), uuid.uuid4(), weight=70.0)

    token = make_context_token(sub=uuid.uuid4(), account_id=uuid.uuid4(), scopes=_RW)
    resp = await raw_client.get("/api/v1/profiles/me", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.unit
async def test_read_scope_cannot_write(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """Un token profile:read seul lit le dossier mais ne peut pas l'écrire (403)."""
    acc = uuid.uuid4()
    await _insert_profile(session, acc, uuid.uuid4(), weight=70.0)
    token = make_context_token(sub=uuid.uuid4(), account_id=acc, scopes=["profile:read"])

    assert (
        await raw_client.get("/api/v1/profiles/me", headers=_auth(token))
    ).status_code == 200
    patch = await raw_client.patch(
        "/api/v1/profiles/me", json={"weight_kg": 80.0}, headers=_auth(token)
    )
    assert patch.status_code == 403


@pytest.mark.unit
async def test_write_scope_can_write(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """Un token profile:write peut mettre à jour le dossier du compte actif."""
    acc = uuid.uuid4()
    await _insert_profile(session, acc, uuid.uuid4(), weight=70.0)
    token = make_context_token(sub=uuid.uuid4(), account_id=acc, scopes=_RW)

    resp = await raw_client.patch(
        "/api/v1/profiles/me", json={"weight_kg": 82.0}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert resp.json()["weight_kg"] == pytest.approx(82.0, abs=0.01)


@pytest.mark.unit
async def test_token_without_account_context_is_forbidden(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """Un token sans act_account ne peut pas accéder aux routes de dossier (403)."""
    token = make_context_token(sub=uuid.uuid4(), account_id=None, scopes=_RW)
    resp = await raw_client.get("/api/v1/profiles/me", headers=_auth(token))
    assert resp.status_code == 403


@pytest.mark.unit
async def test_subresource_is_isolated_by_account(
    raw_client: AsyncClient, session: AsyncSession
) -> None:
    """Une blessure ajoutée sur le compte A n'apparaît pas sur le compte B."""
    acc_a, acc_b = uuid.uuid4(), uuid.uuid4()
    await _insert_profile(session, acc_a, uuid.uuid4(), weight=70.0)
    await _insert_profile(session, acc_b, uuid.uuid4(), weight=70.0)
    token_a = make_context_token(sub=uuid.uuid4(), account_id=acc_a, scopes=_RW)
    token_b = make_context_token(sub=uuid.uuid4(), account_id=acc_b, scopes=_RW)

    created = await raw_client.post(
        "/api/v1/profiles/me/injuries",
        json={"body_part": "cheville", "injury_type": "entorse"},
        headers=_auth(token_a),
    )
    assert created.status_code == 201

    list_a = await raw_client.get("/api/v1/profiles/me/injuries", headers=_auth(token_a))
    list_b = await raw_client.get("/api/v1/profiles/me/injuries", headers=_auth(token_b))
    assert len(list_a.json()) == 1
    assert list_b.json() == []
