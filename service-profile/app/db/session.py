"""Factory de sessions SQLAlchemy asynchrones."""
import logging
from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Crée et met en cache l'AsyncEngine. Normalise l'URL pour asyncpg."""
    logger.debug("Initialisation du moteur SQLAlchemy async")
    return create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.DEBUG,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Crée et met en cache la factory de sessions."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI : fournit une AsyncSession dans un context manager."""
    async with _session_factory()() as session:
        yield session