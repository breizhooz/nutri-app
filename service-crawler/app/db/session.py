from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )

@lru_cache(maxsize=1)
def _session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with _session_factory()() as session:
        yield session