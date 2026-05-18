# service-crawler/tests/unit/conftest.py
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("MINIO_BUCKET_CRAWLER", "crawler-test")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("SERVICE_RECIPE_TOKEN", "test-service-token")
os.environ.setdefault("SERVICE_NOTIFICATION_URL", "http://service-notification-test:8006")
os.environ.setdefault("SERVICE_NOTIFICATION_TOKEN", "test-notification-token")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests")

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.crawl_source import CrawlSource  # noqa: F401

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
_SQLITE_TABLES = [CrawlSource.__table__]

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_JWT_SECRET = "test-jwt-secret-for-unit-tests"


@compiles(PG_UUID, "sqlite")
def _compile_pg_uuid_sqlite(element, compiler, **kw):
    return "CHAR(32)"


def make_test_token(user_id: uuid.UUID = TEST_USER_ID) -> str:
    """Génère un token JWT valide pour les tests."""
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
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=_SQLITE_TABLES)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=_SQLITE_TABLES)
    await engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    token = make_test_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
