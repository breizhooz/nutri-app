import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

# Must be set before any app module is imported
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("MINIO_BUCKET_CRAWLER", "crawler-test")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.crawl_source import CrawlSource  # noqa: F401 — registers table in metadata

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Tables that are SQLite-compatible (excludes crawl_results which uses ARRAY)
_SQLITE_TABLES = [CrawlSource.__table__]


# postgresql.UUID uses NUMERIC affinity in SQLite (type "UUID" is unrecognised),
# which silently coerces all-numeric hex strings to integers. Force TEXT affinity
# via CHAR(32) so values round-trip through the bind/result processors correctly.
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

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()