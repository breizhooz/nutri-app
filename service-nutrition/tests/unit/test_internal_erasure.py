"""Tests de l'endpoint interne d'effacement RGPD (art. 17) — service-nutrition."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models.macro_error import MacroError

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")
TEST_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-0000000002a1")
OTHER_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-0000000002a2")


async def _seed(db_session, slug, user_id, account_id) -> None:
    db_session.add(
        MacroError(
            slug=slug,
            user_id=user_id,
            account_id=account_id,
            raw_ingredient="gochujang",
        )
    )
    await db_session.commit()


@pytest.mark.unit
async def test_erasure_removes_macro_errors_by_account(service_client, db_session):
    """L'effacement supprime les macro_errors du compte ciblé uniquement."""
    await _seed(db_session, "me-1", TEST_USER_ID, TEST_ACCOUNT_ID)
    await _seed(db_session, "me-2", TEST_USER_ID, TEST_ACCOUNT_ID)
    await _seed(db_session, "me-3", OTHER_USER_ID, OTHER_ACCOUNT_ID)

    resp = await service_client.post(
        "/api/v1/internal/erasure", json={"account_ids": [str(TEST_ACCOUNT_ID)]}
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2

    remaining = (
        await db_session.execute(select(func.count()).select_from(MacroError))
    ).scalar()
    assert remaining == 1


@pytest.mark.unit
async def test_erasure_removes_by_user_id_when_account_missing(
    service_client, db_session
):
    """Les lignes sans account_id (legacy) sont purgées via user_id."""
    await _seed(db_session, "me-legacy", TEST_USER_ID, None)

    resp = await service_client.post(
        "/api/v1/internal/erasure",
        json={"account_ids": [], "user_id": str(TEST_USER_ID)},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1


@pytest.mark.unit
async def test_erasure_is_idempotent(service_client, db_session):
    """Un second appel ne supprime rien (deleted=0)."""
    await _seed(db_session, "me-1", TEST_USER_ID, TEST_ACCOUNT_ID)
    body = {"account_ids": [str(TEST_ACCOUNT_ID)]}

    first = await service_client.post("/api/v1/internal/erasure", json=body)
    assert first.json()["deleted"] == 1
    second = await service_client.post("/api/v1/internal/erasure", json=body)
    assert second.status_code == 200
    assert second.json()["deleted"] == 0


@pytest.mark.unit
async def test_erasure_rejects_user_token(client):
    """Un JWT utilisateur (et non un token de service) est refusé (403)."""
    resp = await client.post(
        "/api/v1/internal/erasure", json={"account_ids": [str(TEST_ACCOUNT_ID)]}
    )
    assert resp.status_code == 403
