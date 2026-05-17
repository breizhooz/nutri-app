"""Tests unitaires — PushRepository (SQLite in-memory)."""
import os
import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Variables d'env avant tout import d'app (conftest.py les setdefault aussi,
# mais on s'assure ici que ce module peut tourner seul)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test")
os.environ.setdefault("MINIO_SECRET_KEY", "test")
os.environ.setdefault("MINIO_BUCKET_CRAWLER", "test")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://localhost:8000")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.db.base_class import Base
from app.models.enums import PushChannel
from app.models.push_subscription import PushSubscription  # noqa: F401
from app.repositories.push_repository import PushRepository

_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def push_session():
    """Session SQLite isolée pour les tests PushRepository."""
    engine = create_async_engine(_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all, tables=[PushSubscription.__table__]
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.drop_all, tables=[PushSubscription.__table__]
        )
    await engine.dispose()


@pytest.fixture
def uid_a() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


@pytest.fixture
def uid_b() -> uuid.UUID:
    return uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")


# ─── upsert ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_upsert_creates_subscription(push_session, uid_a):
    sub = await PushRepository(push_session).upsert(
        uid_a, PushChannel.EXPO, "ExponentPushToken[abc]"
    )
    assert sub.id is not None
    assert sub.user_id == uid_a
    assert sub.channel == PushChannel.EXPO
    assert sub.token == "ExponentPushToken[abc]"


@pytest.mark.anyio
async def test_upsert_is_idempotent(push_session, uid_a):
    repo = PushRepository(push_session)
    sub1 = await repo.upsert(uid_a, PushChannel.EXPO, "token-x")
    sub2 = await repo.upsert(uid_a, PushChannel.EXPO, "token-x")
    assert sub1.id == sub2.id
    assert len(await repo.get_by_user_id(uid_a)) == 1


@pytest.mark.anyio
async def test_upsert_distinct_tokens_creates_two(push_session, uid_a):
    repo = PushRepository(push_session)
    await repo.upsert(uid_a, PushChannel.EXPO, "token-1")
    await repo.upsert(uid_a, PushChannel.EXPO, "token-2")
    assert len(await repo.get_by_user_id(uid_a)) == 2


@pytest.mark.anyio
async def test_upsert_web_push_channel(push_session, uid_a):
    token = '{"endpoint":"https://fcm.example.com","keys":{"p256dh":"k","auth":"a"}}'
    sub = await PushRepository(push_session).upsert(uid_a, PushChannel.WEB_PUSH, token)
    assert sub.channel == PushChannel.WEB_PUSH


# ─── delete_by_token ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_delete_existing_returns_true(push_session, uid_a):
    repo = PushRepository(push_session)
    await repo.upsert(uid_a, PushChannel.EXPO, "del-me")
    assert await repo.delete_by_token(uid_a, "del-me") is True
    assert await repo.get_by_user_id(uid_a) == []


@pytest.mark.anyio
async def test_delete_nonexistent_returns_false(push_session, uid_a):
    assert await PushRepository(push_session).delete_by_token(uid_a, "ghost") is False


@pytest.mark.anyio
async def test_delete_only_targets_correct_user(push_session, uid_a, uid_b):
    repo = PushRepository(push_session)