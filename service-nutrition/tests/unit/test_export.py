"""Tests de l'export RGPD (art. 20) — service-nutrition."""

import uuid

import pytest

from app.models.macro_error import MacroError
from app.repositories.export_repository import ExportRepository


def _macro(slug, *, user_id=None, account_id=None):
    return MacroError(
        slug=slug,
        user_id=user_id or uuid.uuid4(),
        account_id=account_id,
        raw_ingredient="gochujang",
    )


@pytest.mark.unit
async def test_export_by_account(db_session):
    """L'export renvoie les macro_errors du compte ciblé."""
    acc = uuid.uuid4()
    db_session.add_all(
        [_macro("me-1", account_id=acc), _macro("me-2", account_id=uuid.uuid4())]
    )
    await db_session.commit()

    data = await ExportRepository(db_session).export_by_accounts([acc])
    assert {m["slug"] for m in data["macro_errors"]} == {"me-1"}


@pytest.mark.unit
async def test_export_by_user(db_session):
    """L'export résout aussi par user_id (clé legacy)."""
    uid = uuid.uuid4()
    db_session.add(_macro("me-user", user_id=uid))
    await db_session.commit()

    data = await ExportRepository(db_session).export_by_accounts([], user_id=uid)
    assert {m["slug"] for m in data["macro_errors"]} == {"me-user"}


@pytest.mark.unit
async def test_export_empty_when_no_match(db_session):
    """Aucune clé / aucun match → liste vide."""
    assert await ExportRepository(db_session).export_by_accounts([]) == {
        "macro_errors": []
    }
