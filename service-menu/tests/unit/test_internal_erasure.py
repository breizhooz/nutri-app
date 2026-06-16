"""Tests de l'endpoint interne d'effacement RGPD (art. 17) — service-menu."""

import os
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("SERVICE_USER_URL", "http://service-user-test:8000")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("SERVICE_MENU_TOKEN", "test-menu-service-token")

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.menu_slot import MenuSlot
from app.models.weekly_menu import WeeklyMenu

_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = async_sessionmaker(_ENGINE, expire_on_commit=False)
_TOKEN = "test-menu-service-token"


@pytest.fixture(autouse=True)
async def _db():
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def session():
    async with _Session() as s:
        yield s


@pytest.fixture
async def service_client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _add_menu(session, account_id: str, slug: str) -> None:
    menu = WeeklyMenu(
        slug=slug,
        user_id=account_id,  # distinct par compte → respecte uq(user_id, start_date)
        account_id=account_id,
        nb_persons=1,
        start_date=date(2026, 6, 2),
        exclusions=[],
        free_tags={},
    )
    session.add(menu)
    await session.flush()
    session.add(
        MenuSlot(
            menu_id=menu.id,
            day_of_week="enums.day.monday",
            meal_type="enums.meal_type.lunch",
            recipe_id=1,
            nb_persons=1,
        )
    )
    await session.commit()


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar()


@pytest.mark.unit
async def test_erasure_removes_menus_and_slots(service_client, session):
    """L'effacement supprime les menus du compte ciblé et leurs créneaux."""
    acc = str(uuid.uuid4())
    other = str(uuid.uuid4())
    await _add_menu(session, acc, "menu-a")
    await _add_menu(session, other, "menu-b")

    resp = await service_client.post(
        "/api/v1/internal/erasure", json={"account_ids": [acc]}
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1
    # Seul le menu de l'autre compte subsiste.
    assert await _count(session, WeeklyMenu) == 1
    assert await _count(session, MenuSlot) == 1


@pytest.mark.unit
async def test_erasure_is_idempotent(service_client, session):
    """Un second appel ne supprime rien (deleted=0)."""
    acc = str(uuid.uuid4())
    await _add_menu(session, acc, "menu-a")
    body = {"account_ids": [acc]}

    first = await service_client.post("/api/v1/internal/erasure", json=body)
    assert first.json()["deleted"] == 1
    second = await service_client.post("/api/v1/internal/erasure", json=body)
    assert second.status_code == 200
    assert second.json()["deleted"] == 0


@pytest.mark.unit
async def test_erasure_requires_service_token(session):
    """Sans token de service, l'accès est refusé (403)."""

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/v1/internal/erasure", json={"account_ids": [str(uuid.uuid4())]}
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403
