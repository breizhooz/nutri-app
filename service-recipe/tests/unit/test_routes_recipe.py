import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.http_client import get_user_client
from app.main import app
from app.db.session import get_session
from app.models.enums import CuisineOrigin, CourseType


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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
async def test_create_recipe_with_valid_user_returns_201(override_db, override_user_client_exists):
    from datetime import datetime

    async def mock_refresh(obj):
        obj.id = 1
        obj.created_at = datetime(2026, 1, 1, 12, 0, 0)
        obj.updated_at = datetime(2026, 1, 1, 12, 0, 0)
        obj.recipe_ingredients = []
        if obj.cuisine_origin is None:
            obj.cuisine_origin = CuisineOrigin.FRENCH
        if obj.course_type is None:
            obj.course_type = CourseType.MAIN_COURSE
        if obj.tags is None:
            obj.tags = {}
    override_db.refresh.side_effect = mock_refresh  # ← injecté sur le mock_session

    payload = {
        "title": "Poulet rôti",
        "instructions": "Cuire au four 1h à 180°C.",
        "recipe_ingredients": [],
        "created_by_user_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/recipe", json=payload)

    assert response.status_code == 201
    override_user_client_exists.user_exist.assert_called_once_with(
        "123e4567-e89b-12d3-a456-426614174000"
    )
