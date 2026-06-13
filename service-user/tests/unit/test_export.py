"""Tests de l'export RGPD (art. 20) + claim health_consent — service-user."""

import uuid

import pytest

from app.models.access import Account
from app.models.consent import CONSENT_HEALTH_DATA
from app.models.user import User
from app.services.access_service import AccessService
from app.services.consent_service import ConsentService
from app.services.export_service import ExportService


class _FakeExportClient:
    """ExportClient factice : renvoie une charge canned par service."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], str | None]] = []

    async def export(self, service, account_ids, user_id):
        self.calls.append((service, account_ids, user_id))
        return {"rows": [f"{service}-data"]}


@pytest.mark.unit
async def test_build_login_claims_carries_health_consent(db_session):
    """Le claim health_consent reflète l'état du consentement santé."""
    user = User(email="claims@x.io", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    claims = await AccessService(db_session).build_login_claims(user)
    assert claims["health_consent"] is False

    await ConsentService(db_session).record(
        user.id, CONSENT_HEALTH_DATA, "v1", granted=True
    )
    claims = await AccessService(db_session).build_login_claims(user)
    assert claims["health_consent"] is True


@pytest.mark.unit
async def test_build_export_aggregates_identity_and_services(db_session):
    """L'export contient l'identité (sans secrets) et les données cross-service."""
    user = User(email="export@x.io", hashed_password="secret-hash")
    db_session.add(user)
    await db_session.flush()
    account = Account(name="perso", created_by=user.id)
    db_session.add(account)
    await db_session.flush()
    user.default_account_id = account.id
    await db_session.commit()

    await ConsentService(db_session).record(
        user.id, CONSENT_HEALTH_DATA, "v1", granted=True
    )

    fake = _FakeExportClient()
    export = await ExportService(db_session, client=fake).build_export(user)

    # Identité présente, secrets exclus.
    assert export["user"]["identity"]["email"] == "export@x.io"
    assert "hashed_password" not in export["user"]["identity"]
    assert len(export["user"]["consents"]) == 1

    # Tous les services détenteurs ont été interrogés.
    assert set(export["services"]) == {"profile", "menu", "notification", "nutrition"}
    assert export["services"]["profile"] == {"rows": ["profile-data"]}
    # account_id du compte perso transmis aux services.
    assert fake.calls[0][1] == [str(account.id)]


@pytest.mark.unit
async def test_build_export_records_service_error(db_session):
    """Un service en échec n'interrompt pas l'export : entrée 'error'."""

    class _FailingClient:
        async def export(self, service, account_ids, user_id):
            raise RuntimeError("boom")

    user = User(email="fail@x.io", hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    export = await ExportService(db_session, client=_FailingClient()).build_export(user)
    assert export["services"]["profile"]["error"] == "boom"
