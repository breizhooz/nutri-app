"""Configuration des fixtures pytest pour le service-profile."""

import os
import uuid
from collections.abc import AsyncGenerator

# Variables d'environnement AVANT tout import de l'application
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("SERVICE_PROFILE_TOKEN", "test-service-token-12345")

# Clé Fernet jetable pour le chiffrement at-rest des champs santé en test.
from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("PROFILE_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from nutri_shared.core.context import AccessContext

from app.core.deps import (
    get_read_account_id,
    get_write_account_id,
    get_write_context,
    require_health_consent,
)
from app.db.base import Base
from app.db.session import get_session
from app.main import app

# Scopes complets accordés au contexte de test (OWNER-like).
_TEST_SCOPES = frozenset(
    {"profile:read", "profile:write", "recipe:read", "plan:read", "journal:read"}
)


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


@pytest.fixture
def test_account_id() -> uuid.UUID:
    """Compte actif unique par test (multicomptes) — clé de partition du dossier."""
    return uuid.uuid4()


def make_context_token(
    *,
    sub: uuid.UUID,
    account_id: uuid.UUID | None,
    scopes: list[str],
    user_admin: bool = False,
) -> str:
    """Forge un JWT d'accès de contexte (act_account + scopes) pour les tests.

    Permet de tester l'enforcement réel de require_scope et l'isolation par
    compte, sans passer par les overrides du fixture ``client``.
    """
    import jwt
    from datetime import datetime, timedelta, timezone

    payload: dict = {
        "sub": str(sub),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "scopes": scopes,
        "user_admin": user_admin,
        "user_right": {},
        # Token « pleinement autorisé » par défaut : le consentement santé (art. 9)
        # est testé séparément (test_health_consent_guard) avec des tokens dédiés.
        "health_consent": True,
    }
    if account_id is not None:
        payload["act_account"] = str(account_id)
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest_asyncio.fixture
async def raw_client(
    session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Client à authentification réelle : seul get_session est overridé.

    Les routes appliquent leur vrai require_scope / résolution de compte ; les
    tests fournissent un Bearer forgé par requête (cf. make_context_token).
    """

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


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
    session: AsyncSession, test_user_id: uuid.UUID, test_account_id: uuid.UUID
) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP de test : session DB + contexte de compte injectés.

    Multicomptes : le contexte de test agit sur ``test_account_id`` (clé de
    partition du dossier) en tant qu'identité ``test_user_id`` (auteur). Le
    dossier créé via l'API porte donc ``account_id=test_account_id`` ET
    ``user_id=test_user_id`` (ce dernier sert aux endpoints inter-service).
    """

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def _override_read_account() -> uuid.UUID:
        return test_account_id

    async def _override_write_account() -> uuid.UUID:
        return test_account_id

    async def _override_write_context() -> AccessContext:
        return AccessContext(
            sub=str(test_user_id),
            account_id=str(test_account_id),
            scopes=_TEST_SCOPES,
            user_admin=False,
            capabilities={},
        )

    # Garde RGPD (art. 9) neutralisée ici : ce fixture teste la logique métier,
    # pas le consentement (couvert séparément avec raw_client + tokens forgés).
    async def _override_health_consent() -> None:
        return None

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_read_account_id] = _override_read_account
    app.dependency_overrides[get_write_account_id] = _override_write_account
    app.dependency_overrides[get_write_context] = _override_write_context
    app.dependency_overrides[require_health_consent] = _override_health_consent

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
