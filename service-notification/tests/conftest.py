import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
import jwt
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

# Variables d'environnement forcées — doivent être définies avant tout import applicatif
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["VAPID_PRIVATE_KEY"] = "test-vapid-private-key"
os.environ["VAPID_PUBLIC_KEY"] = "test-vapid-public-key"
os.environ["VAPID_CLAIMS_EMAIL"] = "test@nutriplanner.app"
os.environ["SERVICE_NOTIFICATION_TOKEN"] = "test-service-token"

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_JWT_SECRET = "test-jwt-secret"


# SQLite ne connaît pas le type UUID PostgreSQL — on le remplace par CHAR(32)
@compiles(PG_UUID, "sqlite")
def _pg_uuid_to_char(element, compiler, **kw):
    return "CHAR(32)"


def make_test_token(user_id: uuid.UUID = TEST_USER_ID) -> str:
    """Génère un JWT valide pour les tests."""
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def db_session():
    """Session SQLite in-memory, tables créées/supprimées par test."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Client HTTP avec JWT utilisateur valide."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {make_test_token()}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def service_client(db_session: AsyncSession):
    """Client HTTP avec token de service (appels inter-services)."""
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test-service-token"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()