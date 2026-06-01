import os
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("MINIO_BUCKET_CRAWLER", "crawler-test")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("SERVICE_RECIPE_TOKEN", "test-service-token")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests")
os.environ.setdefault("INSTAGRAM_USERNAME", "")
os.environ.setdefault("INSTAGRAM_PASSWORD", "")
os.environ.setdefault("INSTAGRAM_SESSION_FILE", "/tmp/test_instagram_session")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GROQ_MODEL", "llama-3.1-8b-instant")

from app.core.deps import get_current_user_id, get_token_payload
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.crawl_source import CrawlSource  # noqa: F401

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
_SQLITE_TABLES = [CrawlSource.__table__]

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@compiles(PG_UUID, "sqlite")
def _compile_pg_uuid_sqlite(element, compiler, **kw):
    return "CHAR(32)"


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

    async def override_get_current_user_id() -> uuid.UUID:
        return TEST_USER_ID

    async def override_get_token_payload() -> dict:
        # Utilisateur de test disposant de tous les droits (crawl + uniq_link).
        return {
            "sub": str(TEST_USER_ID),
            "type": "access",
            "user_admin": False,
            "user_right": {
                "crawl": {"instagram": True, "web": True},
                "uniq_link": {"instagram": True, "web": True},
            },
        }

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_token_payload] = override_get_token_payload
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
