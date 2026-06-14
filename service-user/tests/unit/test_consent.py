"""Tests du consentement RGPD (art. 9, Phase 2) — service-user."""

import uuid

import pytest

from app.models.consent import CONSENT_HEALTH_DATA
from app.services.consent_service import ConsentService


@pytest.mark.unit
async def test_record_and_is_active(db_session):
    """Un octroi rend le consentement actif ; un retrait le désactive."""
    svc = ConsentService(db_session)
    uid = uuid.uuid4()

    await svc.record(uid, CONSENT_HEALTH_DATA, "v1", granted=True)
    assert await svc.is_active(uid, CONSENT_HEALTH_DATA) is True
    assert await svc.has_active_health_consent(uid) is True

    await svc.record(uid, CONSENT_HEALTH_DATA, "v1", granted=False)
    assert await svc.is_active(uid, CONSENT_HEALTH_DATA) is False
    assert await svc.has_active_health_consent(uid) is False


@pytest.mark.unit
async def test_list_current_keeps_latest_per_type(db_session):
    """list_current ne renvoie que la dernière trace de chaque type."""
    svc = ConsentService(db_session)
    uid = uuid.uuid4()
    await svc.record(uid, CONSENT_HEALTH_DATA, "v1", granted=True)
    await svc.record(uid, CONSENT_HEALTH_DATA, "v2", granted=False)
    await svc.record(uid, "marketing", "v1", granted=True)

    current = await svc.list_current(uid)
    by_type = {c.consent_type: c for c in current}
    assert set(by_type) == {CONSENT_HEALTH_DATA, "marketing"}
    assert by_type[CONSENT_HEALTH_DATA].version == "v2"
    assert by_type[CONSENT_HEALTH_DATA].granted is False


@pytest.mark.unit
async def test_no_consent_is_inactive(db_session):
    """Sans aucune trace, le consentement n'est pas actif."""
    svc = ConsentService(db_session)
    assert await svc.has_active_health_consent(uuid.uuid4()) is False
