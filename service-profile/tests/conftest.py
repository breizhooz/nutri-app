"""Configuration des fixtures pytest pour le service-profile."""

import os
import uuid
from collections.abc import AsyncGenerator

# Variables d'environnement AVANT tout import de l'application
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("SERVICE_PROFILE_TOKEN", "test-service-token-12345")

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user_id
from app.db.base import Base
from app.db.session import get_session
from app.main import app


@compiles(PG_UUID, "sqlite")
def _pg_uuid_sqlite(element, compiler, **kw) -> str:
    """Mappe UUID PostgreSQL vers CHAR(32) pour la compatibilité SQLite."""
    return "CHAR(32)"


_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    echo=False,
)
_test_factory = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None, None]:
    """Crée toutes les tables une seule fois pour la session de tests."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Session SQLAlchemy fraîche par test, sans rollback.

    L'isolation est garantie par un uuid.uuid4() unique par test —
    les données de tests différents ne se croisent jamais.
    """
    async with _test_factory() as s:
        yield s


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """UUID unique par test pour l'isolation des données sans rollback."""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def service_client() -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP inter-service authentifié par SERVICE_PROFILE_TOKEN."""
    token = os.environ["SERVICE_PROFILE_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def client(
    session: AsyncSession, test_user_id: uuid.UUID
) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP de test avec session DB et user_id injectés via dependency_overrides."""

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        """Remplace get_session par la session de test."""
        yield session

    async def _override_user_id() -> uuid.UUID:
        """Remplace get_current_user_id par l'UUID de test."""
        return test_user_id

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_user_id] = _override_user_id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
