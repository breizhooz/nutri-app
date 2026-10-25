import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _database_url() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Moteur partagé du process API (une seule boucle asyncio : celle d'uvicorn).

    Ne PAS l'utiliser dans une tâche Celery : cf. ``task_session``.
    """
    # Écho SQL : opt-in explicite (SQL_ECHO), découplé de DEBUG — sinon chaque
    # requête SQL était loguée dès que DEBUG=True.
    echo = os.environ.get("SQL_ECHO", "false").lower() in ("true", "1")
    return create_async_engine(_database_url(), echo=echo, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with _session_factory()() as session:
        yield session


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Session pour une tâche Celery (``asyncio.run`` dans un process worker).

    Chaque ``asyncio.run`` crée une NOUVELLE boucle. Le moteur partagé
    (``get_engine``, mis en cache par process) garde des connexions liées à la
    boucle de la 1re tâche → dès la 2e : « Future attached to a different loop ».
    D'où un moteur dédié, sans pool (``NullPool``), fermé en fin de tâche.
    """
    engine = create_async_engine(_database_url(), poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()
