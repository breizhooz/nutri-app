"""Tests de la purge de rétention (RGPD art. 5.1.e, Phase 4) — service-nutrition."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.macro_error import MacroError
from app.services import retention_service


def _dt(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _macro(slug: str, created_at: datetime) -> MacroError:
    return MacroError(
        slug=slug,
        user_id=uuid.uuid4(),
        raw_ingredient="gochujang",
        created_at=created_at,
    )


@pytest.mark.unit
async def test_purge_old_macro_errors(db_session):
    """Seuls les macro_errors au-delà de la rétention sont supprimés."""
    db_session.add_all(
        [
            _macro("me-old", _dt(-120)),
            _macro("me-recent", _dt(-10)),
        ]
    )
    await db_session.commit()

    deleted = await retention_service.purge_old_macro_errors(
        db_session, retention_days=90
    )
    assert deleted == 1
    remaining = (await db_session.execute(select(MacroError.slug))).scalars().all()
    assert remaining == ["me-recent"]


@pytest.mark.unit
async def test_purge_is_idempotent(db_session):
    """Aucun ancien diagnostic → rien à supprimer (idempotent)."""
    db_session.add(_macro("me-recent", _dt(-1)))
    await db_session.commit()

    deleted = await retention_service.purge_old_macro_errors(
        db_session, retention_days=90
    )
    assert deleted == 0
