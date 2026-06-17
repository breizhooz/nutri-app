"""Tests des tâches Celery de rétention (wrappers) — service-user.

Les wrappers de ``app/tasks/retention.py`` ouvrent une session dédiée puis
délèguent à ``retention_service`` (lui-même testé dans ``test_retention.py``).
On neutralise ``_session_factory`` et on remplace les fonctions de service par
des doublures async pour valider le câblage (session ouverte, valeur relayée).
"""

from contextlib import asynccontextmanager

import pytest

from app.tasks import retention as retention_task


class _SentinelSession:
    """Marqueur : ce que ``_session_factory()()`` doit fournir à la tâche."""


@pytest.fixture
def fake_session(monkeypatch):
    """Remplace l'ouverture de session par un context manager async inerte."""
    session = _SentinelSession()

    @asynccontextmanager
    async def _cm():
        yield session

    # _run() fait `_session_factory()()` : le 1er appel rend la factory,
    # le 2nd ouvre la session.
    monkeypatch.setattr(retention_task, "_session_factory", lambda: _cm)
    return session


@pytest.mark.unit
def test_purge_expired_auth_tokens_task(monkeypatch, fake_session):
    async def _fake(session):
        assert session is fake_session
        return 7

    monkeypatch.setattr(
        retention_task.retention_service, "purge_expired_auth_tokens", _fake
    )
    assert retention_task.purge_expired_auth_tokens() == 7


@pytest.mark.unit
def test_purge_stale_invitations_task(monkeypatch, fake_session):
    captured = {}

    async def _fake(session, retention_days):
        captured["days"] = retention_days
        return 3

    monkeypatch.setattr(
        retention_task.retention_service, "purge_stale_invitations", _fake
    )
    assert retention_task.purge_stale_invitations() == 3
    assert captured["days"] == retention_task.settings.INVITATION_RETENTION_DAYS


@pytest.mark.unit
def test_purge_old_audit_logs_task(monkeypatch, fake_session):
    captured = {}

    async def _fake(session, retention_days):
        captured["days"] = retention_days
        return 5

    monkeypatch.setattr(retention_task.retention_service, "purge_old_audit_logs", _fake)
    assert retention_task.purge_old_audit_logs() == 5
    assert captured["days"] == retention_task.settings.AUDIT_LOG_RETENTION_DAYS


@pytest.mark.unit
def test_purge_inactive_accounts_task(monkeypatch, fake_session):
    captured = {}

    async def _fake(session, retention_days):
        captured["days"] = retention_days
        return 2

    monkeypatch.setattr(
        retention_task.retention_service, "purge_inactive_accounts", _fake
    )
    assert retention_task.purge_inactive_accounts() == 2
    assert captured["days"] == retention_task.settings.INACTIVE_ACCOUNT_RETENTION_DAYS
