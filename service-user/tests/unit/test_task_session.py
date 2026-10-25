"""Sessions des tâches Celery : ``task_session`` (nutri_shared) + câblage.

Régression évitée : les tâches utilisaient le moteur partagé du process
(``get_engine``, en cache). Chaque tâche faisant ``asyncio.run`` (nouvelle
boucle), dès la 2e tâche d'un même worker asyncpg levait « Future attached to a
different loop » → effacement RGPD et purges en échec. (aiosqlite ne reproduit
pas ce bug propre à asyncpg : la preuve runtime a été faite sur PostgreSQL.)
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

import nutri_shared.db.session as shared_session
from app.tasks import erasure as erasure_task


@pytest.mark.unit
async def test_task_session_uses_dedicated_nullpool_engine_and_disposes_it(
    monkeypatch,
):
    engine = MagicMock()
    engine.dispose = AsyncMock()
    created = {}

    def _fake_create(url, **kwargs):
        created.update(url=url, **kwargs)
        return engine

    monkeypatch.setattr(shared_session, "create_async_engine", _fake_create)
    monkeypatch.setattr(shared_session, "async_sessionmaker", MagicMock())

    async with shared_session.task_session():
        pass

    assert created["poolclass"] is NullPool  # pas de connexion réutilisée entre boucles
    engine.dispose.assert_awaited_once()


@pytest.mark.unit
def test_task_session_works_across_successive_event_loops(tmp_path, monkeypatch):
    """Comme un worker : plusieurs asyncio.run() successifs dans le même process."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite'}")

    async def _query() -> int:
        async with shared_session.task_session() as session:
            return (await session.execute(text("select 1"))).scalar()

    assert [asyncio.run(_query()) for _ in range(3)] == [1, 1, 1]


@pytest.mark.unit
async def test_erasure_task_opens_a_task_session(monkeypatch):
    sentinel = object()

    @asynccontextmanager
    async def _fake_task_session():
        yield sentinel

    received = {}

    async def _fake_process(session, request_id):
        received.update(session=session, request_id=request_id)
        return []

    monkeypatch.setattr(erasure_task, "task_session", _fake_task_session)
    monkeypatch.setattr(
        erasure_task.erasure_service, "process_erasure_request", _fake_process
    )
    request_id = uuid.uuid4()

    assert await erasure_task._process(str(request_id)) == []
    assert received == {"session": sentinel, "request_id": request_id}
