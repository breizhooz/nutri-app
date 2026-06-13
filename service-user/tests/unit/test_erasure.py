"""Tests de l'orchestration d'effacement RGPD (art. 17) — service-user."""

import uuid

import pytest
from sqlalchemy import select

from app.models.access import Account, AuditLog
from app.models.erasure import ErasureTarget
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services import erasure_service
from app.services.erasure_client import ERASURE_SERVICES
from app.services.user_service import UserService


class _FakeClient:
    """ErasureClient factice : enregistre les appels et simule des échecs."""

    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.calls: list[tuple[str, list[str], str | None]] = []
        self._fail_for = fail_for or set()

    async def erase(self, service, account_ids, user_id):
        self.calls.append((service, account_ids, user_id))
        if service in self._fail_for:
            raise RuntimeError("boom")
        return 1


async def _targets(db_session, request_id) -> list[ErasureTarget]:
    result = await db_session.execute(
        select(ErasureTarget).where(ErasureTarget.request_id == request_id)
    )
    return list(result.scalars().all())


@pytest.mark.unit
async def test_request_erasure_creates_journal_and_audit(db_session):
    """request_erasure crée une cible par service + une entrée d'audit."""
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()

    request_id = await erasure_service.request_erasure(
        db_session, user_id, [account_id]
    )

    targets = await _targets(db_session, request_id)
    assert {t.service for t in targets} == set(ERASURE_SERVICES)
    assert all(t.status == "pending" for t in targets)
    assert all(t.account_ids == [str(account_id)] for t in targets)

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "account.erasure_requested")
        )
    ).scalars().all()
    assert len(audit) == 1


@pytest.mark.unit
async def test_process_erasure_marks_all_done(db_session):
    """Tous les services répondent → toutes les cibles passent à done."""
    request_id = await erasure_service.request_erasure(
        db_session, uuid.uuid4(), [uuid.uuid4()]
    )
    fake = _FakeClient()

    failed = await erasure_service.process_erasure_request(
        db_session, request_id, client=fake
    )

    assert failed == []
    assert {c[0] for c in fake.calls} == set(ERASURE_SERVICES)
    targets = await _targets(db_session, request_id)
    assert all(t.status == "done" for t in targets)
    assert all(t.deleted_count == 1 for t in targets)


@pytest.mark.unit
async def test_process_erasure_retries_only_failed(db_session):
    """Un échec partiel n'est pas rejoué sur les cibles déjà done (idempotent)."""
    request_id = await erasure_service.request_erasure(
        db_session, uuid.uuid4(), [uuid.uuid4()]
    )

    failed = await erasure_service.process_erasure_request(
        db_session, request_id, client=_FakeClient(fail_for={"menu"})
    )
    assert failed == ["menu"]

    menu = (
        await db_session.execute(
            select(ErasureTarget).where(
                ErasureTarget.request_id == request_id,
                ErasureTarget.service == "menu",
            )
        )
    ).scalar_one()
    assert menu.status == "failed"
    assert menu.attempts == 1
    assert menu.last_error

    # 2e passage : seule la cible non terminée (menu) est rejouée, et réussit.
    fake2 = _FakeClient()
    failed2 = await erasure_service.process_erasure_request(
        db_session, request_id, client=fake2
    )
    assert failed2 == []
    assert [c[0] for c in fake2.calls] == ["menu"]
    assert menu.status == "done"
    assert menu.attempts == 2


@pytest.mark.unit
async def test_delete_user_triggers_erasure(db_session, monkeypatch):
    """delete_user purge localement et programme l'effacement cross-service."""
    scheduled: list[str] = []
    monkeypatch.setattr(
        erasure_service, "schedule_erasure", lambda rid: scheduled.append(str(rid))
    )

    user = User(email="erase-me@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    account = Account(name="perso", type="personal", created_by=user.id)
    db_session.add(account)
    await db_session.flush()
    user.default_account_id = account.id
    await db_session.commit()

    service = UserService(UserRepository(db_session))
    assert await service.delete_user(user.id) is True

    # Identité + compte personnel supprimés localement.
    assert (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Account).where(Account.id == account.id))
    ).scalar_one_or_none() is None

    # Journal créé (1 cible/service) + tâche programmée.
    targets = (await db_session.execute(select(ErasureTarget))).scalars().all()
    assert {t.service for t in targets} == set(ERASURE_SERVICES)
    assert all(t.account_ids == [str(account.id)] for t in targets)
    assert len(scheduled) == 1
