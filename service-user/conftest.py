"""Pytest configuration — env vars must be set before any app import."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("FACEBOOK_CLIENT_ID", "test-facebook-client-id")
os.environ.setdefault("FACEBOOK_CLIENT_SECRET", "test-facebook-client-secret")
os.environ.setdefault("OAUTH_REDIRECT_BASE_URL", "http://localhost:8001")
os.environ.setdefault(
    "MFA_TOTP_ENCRYPTION_KEY",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)
os.environ.setdefault("NOTIFICATION_SERVICE_URL", "http://localhost:8006")
os.environ.setdefault("NOTIFICATION_SERVICE_TOKEN", "test-notification-token")
os.environ.setdefault("PASSWORD_RESET_BASE_URL", "http://localhost:3000")
os.environ.setdefault("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("PASSWORD_HISTORY_COUNT", "5")

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.password_history import PasswordHistory  # noqa: F401
from app.models.password_reset_token import PasswordResetToken  # noqa: F401


def pytest_configure(config):
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "smoke" in markexpr and "not smoke" not in markexpr:
        try:
            config.option.cov_fail_under = 0.0
        except AttributeError:
            pass


_JWT_SECRET: str = os.environ.get("JWT_SECRET", "test-secret-key-for-testing-only")
_TEST_DB_URL: str = "sqlite+aiosqlite:///:memory:"
TEST_USER_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@compiles(PG_UUID, "sqlite")
def _pg_uuid_to_char(element, compiler, **kw) -> str:  # type: ignore[no-untyped-def]
    """Map PostgreSQL UUID type to CHAR(32) for SQLite test compatibility."""
    return "CHAR(32)"


def make_test_token(user_id: uuid.UUID = TEST_USER_ID) -> str:
    """Generate a signed JWT access token for use in tests.

    Args:
        user_id: UUID to embed as the token subject.

    Returns:
        A signed HS256 JWT string.
    """
    payload: dict = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def make_mfa_token(user_id: uuid.UUID = TEST_USER_ID) -> str:
    """Generate a signed JWT mfa_pending token for use in tests.

    Args:
        user_id: UUID to embed as the token subject.

    Returns:
        A signed HS256 JWT string with type='mfa_pending'.
    """
    payload: dict = {
        "sub": str(user_id),
        "type": "mfa_pending",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="function")
async def db_session() -> AsyncSession:  # type: ignore[misc]
    """Provide a fresh SQLite in-memory session per test function.

    Yields:
        An async SQLAlchemy session backed by SQLite.
    """
    from app.models.mfa_pending_code import MfaPendingCode  # noqa: F401
    from app.models.oauth_account import OAuthAccount  # noqa: F401
    from app.models.user import User  # noqa: F401

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def auth_client(db_session: AsyncSession) -> AsyncClient:  # type: ignore[misc]
    """HTTP test client with a valid user Bearer token.

    Args:
        db_session: The in-memory DB session fixture.

    Yields:
        An httpx.AsyncClient bound to the FastAPI test app.
    """

    async def _override() -> AsyncSession:  # type: ignore[misc]
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
async def anon_client(db_session: AsyncSession) -> AsyncClient:  # type: ignore[misc]
    """HTTP test client without authentication.

    Args:
        db_session: The in-memory DB session fixture.

    Yields:
        An httpx.AsyncClient bound to the FastAPI test app.
    """

    async def _override() -> AsyncSession:  # type: ignore[misc]
        yield db_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Repart d'un compteur de rate-limit vide avant chaque test (SEC-07).

    Les limiteurs sont des singletons de module : sans ce reset, les appels
    cumulés de plusieurs tests partageant la même IP de TestClient pourraient
    déclencher un 429 et rendre la suite instable.
    """
    from app.core import rate_limit

    rate_limit.login_limiter._hits.clear()
    rate_limit.mfa_verify_limiter._hits.clear()
    yield
