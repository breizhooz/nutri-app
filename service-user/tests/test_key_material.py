"""Tests du matériel de clés E2E (Phase 3) — /api/v1/users/me/keys.

Le serveur ne range que des octets opaques (base64) ; il ne dérive ni ne chiffre
rien. On vérifie le round-trip, le cycle de vie (enroll/get/rotate/recovery) et
l'isolation par utilisateur.
"""

import base64
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.models.user import User
from conftest import TEST_USER_ID, make_test_token

_SALT = base64.b64encode(b"\x01" * 16).decode()
_REC_SALT = base64.b64encode(b"\x02" * 16).decode()
_WRAPPED = base64.b64encode(bytes(range(64))).decode()
_WRAPPED_REC = base64.b64encode(bytes(range(64, 128))).decode()
_PARAMS = {"memory_mib": 64, "iterations": 3, "parallelism": 1}

_ENROLL = {
    "salt": _SALT,
    "kdf_params": _PARAMS,
    "wrapped_uk": _WRAPPED,
    "recovery_salt": _REC_SALT,
    "wrapped_uk_recovery": _WRAPPED_REC,
}


async def _seed_user(session: AsyncSession, user_id: uuid.UUID = TEST_USER_ID) -> User:
    user = User(
        id=user_id,
        email=f"{user_id}@test.com",
        hashed_password=hash_password("Pass1234!"),
    )
    session.add(user)
    await session.commit()
    return user


@pytest.mark.unit
async def test_enroll_then_get_roundtrip(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    enroll = await auth_client.post("/api/v1/users/me/keys", json=_ENROLL)
    assert enroll.status_code == 201
    body = enroll.json()
    assert body["salt"] == _SALT
    assert body["wrapped_uk"] == _WRAPPED
    assert body["kdf_params"] == _PARAMS

    get = await auth_client.get("/api/v1/users/me/keys")
    assert get.status_code == 200
    assert get.json()["wrapped_uk"] == _WRAPPED
    # le GET normal ne divulgue pas la voie de récupération
    assert "wrapped_uk_recovery" not in get.json()


@pytest.mark.unit
async def test_recovery_material(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    await auth_client.post("/api/v1/users/me/keys", json=_ENROLL)
    rec = await auth_client.get("/api/v1/users/me/keys/recovery")
    assert rec.status_code == 200
    body = rec.json()
    assert body["recovery_salt"] == _REC_SALT
    assert body["wrapped_uk_recovery"] == _WRAPPED_REC


@pytest.mark.unit
async def test_double_enroll_conflict(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    assert (await auth_client.post("/api/v1/users/me/keys", json=_ENROLL)).status_code == 201
    assert (await auth_client.post("/api/v1/users/me/keys", json=_ENROLL)).status_code == 409


@pytest.mark.unit
async def test_get_before_enroll_404(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    assert (await auth_client.get("/api/v1/users/me/keys")).status_code == 404


@pytest.mark.unit
async def test_rotate_updates_wrap_keeps_recovery(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    await auth_client.post("/api/v1/users/me/keys", json=_ENROLL)

    new_salt = base64.b64encode(b"\x09" * 16).decode()
    new_wrapped = base64.b64encode(b"\xaa" * 64).decode()
    rot = await auth_client.put(
        "/api/v1/users/me/keys",
        json={"salt": new_salt, "kdf_params": _PARAMS, "wrapped_uk": new_wrapped},
    )
    assert rot.status_code == 200
    assert rot.json()["salt"] == new_salt
    assert rot.json()["wrapped_uk"] == new_wrapped
    # la voie de récupération est inchangée (UK identique)
    rec = await auth_client.get("/api/v1/users/me/keys/recovery")
    assert rec.json()["wrapped_uk_recovery"] == _WRAPPED_REC


@pytest.mark.unit
async def test_rotate_before_enroll_404(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    rot = await auth_client.put(
        "/api/v1/users/me/keys",
        json={"salt": _SALT, "kdf_params": _PARAMS, "wrapped_uk": _WRAPPED},
    )
    assert rot.status_code == 404


@pytest.mark.unit
async def test_invalid_base64_400(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_user(db_session)
    bad = {**_ENROLL, "wrapped_uk": "!!! pas du base64 !!!"}
    assert (await auth_client.post("/api/v1/users/me/keys", json=bad)).status_code == 400


@pytest.mark.unit
async def test_isolation_between_users(db_session: AsyncSession) -> None:
    """Le matériel d'un utilisateur n'est pas visible par un autre."""
    user_a = TEST_USER_ID
    user_b = uuid.uuid4()
    await _seed_user(db_session, user_a)
    await _seed_user(db_session, user_b)

    async def _override() -> AsyncSession:  # type: ignore[misc]
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # A inscrit son matériel
            r = await ac.post(
                "/api/v1/users/me/keys",
                json=_ENROLL,
                headers={"Authorization": f"Bearer {make_test_token(user_a)}"},
            )
            assert r.status_code == 201
            # B n'a rien
            r = await ac.get(
                "/api/v1/users/me/keys",
                headers={"Authorization": f"Bearer {make_test_token(user_b)}"},
            )
            assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
