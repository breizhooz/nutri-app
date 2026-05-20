import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
import jwt
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["NUTRITIONIX_BASE_URL"] = "http://nutritionix-test"
os.environ["NUTRITIONIX_APP_ID"] = "test-app-id"
os.environ["NUTRITIONIX_API_KEY"] = "test-api-key"
os.environ["SERVICE_NUTRITION_TOKEN"] = "test-service-token"
os.environ["SERVICE_NOTIFICATION_URL"] = "http://notification-test:8006"
os.environ["SERVICE_NOTIFICATION_TOKEN"] = "test-notif-token"
os.environ["ELASTICSEARCH_URL"] = "http://es-test:9200"

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app as _app  # noqa: E402

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_JWT_SECRET = "test-jwt-secret"


@compiles(PG_UUID, "sqlite")
def _pg_uuid_to_char(element, compiler, **kw):
    return "CHAR(32)"


def make_test_token(user_id: uuid.UUID = TEST_USER_ID) -> str:
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
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def _override():
        yield db_session

    _app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {make_test_token()}"},
    ) as ac:
        yield ac
    _app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def service_client(db_session: AsyncSession):
    async def _override():
        yield db_session

    _app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=_app),
        base_url="http://test",
        headers={"Authorization": "Bearer test-service-token"},
    ) as ac:
        yield ac
    _app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def app(db_session: AsyncSession):
    async def _override():
        yield db_session

    _app.dependency_overrides[get_session] = _override
    yield _app
    _app.dependency_overrides.clear()