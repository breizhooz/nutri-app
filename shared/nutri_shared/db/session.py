import os
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    debug = os.environ.get("DEBUG", "false").lower() in ("true", "1")
    return create_async_engine(database_url, echo=debug, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with _session_factory()() as session:
        yield session
