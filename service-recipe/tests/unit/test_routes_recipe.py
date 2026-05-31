import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.recipes import RecipeServiceFactory
from app.core.http_client import get_user_client
from app.core.deps import get_current_user_id
from app.main import app
from app.db.session import get_session
from app.models.enums import CuisineOrigin, CourseType, DifficultyLevel, RecipeOrigin


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


@pytest.fixture(autouse=False)
def override_db(mock_session):
    async def _get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _get_session
    yield mock_session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_recipe_by_slug_not_found_returns_404(override_db):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    override_db.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recipe/slug-inexistant")

    assert response.status_code == 404


@pytest.fixture
def override_user_client_exists():
    """Simule un service-user qui confirme que l'user existe."""
    mock_client = AsyncMock()
    mock_client.user_exist = AsyncMock(return_value=True)

    async def _get_user_client():
        return mock_client

    app.dependency_overrides[get_user_client] = _get_user_client
    yield mock_client
    app.dependency_overrides.pop(get_user_client, None)


@pytest.mark.asyncio
async def test_create_recipe_with_valid_user_returns_201(override_user_client_exists):
    """create_recipe délègue désormais à RecipeService : on mocke au niveau service."""
    mock_service = AsyncMock()
    mock_service.create.return_value = _make_recipe_response()

    app.dependency_overrides[RecipeServiceFactory.inject] = lambda: mock_service
    app.dependency_overrides[get_current_user_id] = lambda: (
        "123e4567-e89b-12d3-a456-426614174000"
    )

    payload = {
        "title": "Poulet rôti",
        "instructions": "Cuire au four 1h à 180°C.",
        "recipe_ingredients": [],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recipe", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 201
    mock_service.create.assert_called_once()


# ─── POST /manual ─────────────────────────────────────────────────────────────


def _make_recipe_response() -> MagicMock:
    r = MagicMock()
    r.id = 1
    r.title = "Soupe à l'oignon"
    r.slug = "soupe-a-l-oignon"
    r.description = None
    r.instructions = "Faire revenir les oignons."
    r.servings = 4
    r.prep_time_minutes = None
    r.cook_time_minutes = None
    r.difficulty = DifficultyLevel.EASY
    r.cuisine_origin = CuisineOrigin.FRENCH
    r.origin_recipe = RecipeOrigin.PERSONAL
    r.course_type = CourseType.MAIN_COURSE
    r.tags = {}
    r.free_tags = []
    r.book_name = None
    r.source_url = None
    r.image_url = None
    r.image_thumb_url = None
    r.image_suggestions = []
    r.image_search_keyword = None
    r.created_by_user_id = "user-1"
    r.calories_per_serving = None
    r.proteins_per_serving = None
    r.carbs_per_serving = None
    r.fats_per_serving = None
    r.comment = None
    r.rating = None
    r.created_at = datetime(2026, 1, 1, 12, 0, 0)
    r.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    r.recipe_ingredients = []
    return r


@pytest.mark.asyncio
async def test_create_recipe_manual_success():
    mock_service = AsyncMock()
    mock_service.create_manual.return_value = _make_recipe_response()

    app.dependency_overrides[RecipeServiceFactory.inject] = lambda: mock_service
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"

    payload = {
        "title": "Soupe à l'oignon",
        "instructions": "Faire revenir les oignons.",
        "ingredients": [{"name": "oignon", "quantity": 3.0, "unit": "unité"}],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recipe/manual", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 201
    mock_service.create_manual.assert_called_once()
    _, kwargs = mock_service.create_manual.call_args
    assert (
        kwargs.get("user_id") == "user-1"
        or mock_service.create_manual.call_args[0][1] == "user-1"
    )


@pytest.mark.asyncio
async def test_create_recipe_manual_missing_title_returns_422():
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recipe/manual", json={})

    app.dependency_overrides.clear()

    assert response.status_code == 422
