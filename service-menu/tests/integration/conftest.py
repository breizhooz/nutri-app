import pytest
from datetime import date as date_type
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.base import Base
from app.db.session import get_session
from app.core.deps import get_current_user_id
from app.core.http_client import get_recipe_client
from app.models.weekly_menu import WeeklyMenu
from tests.conftest import MockRecipeClient, SAMPLE_RECIPES, RICH_RECIPE

TEST_USER_ID  = "test-user-uuid-1234"
OTHER_USER_ID = "other-user-uuid-9999"

_TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = async_sessionmaker(_TEST_ENGINE, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _dispose_engine():
    yield
    import asyncio
    from app.db.session import get_engine

    async def _cleanup():
        await _TEST_ENGINE.dispose()
        await get_engine().dispose()

    asyncio.run(_cleanup())


@pytest.fixture(autouse=True, scope="function")
async def _reset_db():
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def session(_reset_db) -> AsyncSession:
    async with _TestSession() as sess:
        yield sess


@pytest.fixture
def mock_recipe_client() -> MockRecipeClient:
    return MockRecipeClient(SAMPLE_RECIPES + [RICH_RECIPE])


@pytest.fixture
async def client(session: AsyncSession, mock_recipe_client: MockRecipeClient) -> AsyncClient:
    async def _get_session():
        yield session

    async def _get_recipe_client():
        yield mock_recipe_client

    app.dependency_overrides[get_session]         = _get_session
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_recipe_client]   = _get_recipe_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def other_user_menu(session: AsyncSession) -> WeeklyMenu:
    """Menu appartenant à OTHER_USER_ID, créé via ORM.
    Évite les conflits de dependency_overrides avec le fixture client."""
    menu = WeeklyMenu(
        slug="other-user-menu",
        user_id=OTHER_USER_ID,
        nb_persons=1,
        start_date=date_type(2026, 6, 2),
        exclusions=[],
        free_tags={},
    )
    session.add(menu)
    await session.commit()

    result = await session.execute(
        select(WeeklyMenu)
        .where(WeeklyMenu.id == menu.id)
        .options(selectinload(WeeklyMenu.slots))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

BASE_DATE = "2026-06-02"


def menu_payload(**overrides) -> dict:
    defaults: dict = {
        "start_date": BASE_DATE,
        "nb_persons": 2,
        "slots": [],
    }
    defaults.update(overrides)
    return defaults


def slot_payload(
    day: str = "enums.day.monday",
    meal: str = "enums.meal_type.lunch",
    recipe_id: int = 1,
) -> dict:
    return {"day_of_week": day, "meal_type": meal, "recipe_id": recipe_id}