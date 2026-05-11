import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.session import get_session
from app.core.http_client import get_user_client
from app.models.enums import CuisineOrigin, CourseType, DifficultyLevel, RecipeOrigin


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    null_result = MagicMock()
    null_result.scalar_one_or_none.return_value = None
    session.execute.return_value = null_result
    return session


@pytest.fixture
def override_db(mock_session):
    async def _get_session():
        yield mock_session
    app.dependency_overrides[get_session] = _get_session
    yield mock_session
    app.dependency_overrides.clear()


@pytest.fixture
def override_user_client():
    mock_client = AsyncMock()
    mock_client.user_exist = AsyncMock(return_value=True)
    async def _get_user_client():
        return mock_client
    app.dependency_overrides[get_user_client] = _get_user_client
    yield mock_client
    app.dependency_overrides.pop(get_user_client, None)


@pytest.fixture
def mock_es():
    """Patche le es_client global utilisé par search_service."""
    with patch("app.core.elasticsearch.es_client") as mock:
        mock.index = AsyncMock()
        mock.delete = AsyncMock()
        mock.search = AsyncMock(return_value={
            "hits": {"total": {"value": 0}, "hits": []}
        })
        yield mock


def make_mock_recipe(recipe_id=1, title="Poulet rôti", slug="poulet-roti", recipe_ingredients=None):
    recipe = MagicMock()
    recipe.id = recipe_id
    recipe.title = title
    recipe.slug = slug
    recipe.description = None
    recipe.instructions = "Cuire au four."
    recipe.difficulty = DifficultyLevel.EASY
    recipe.cuisine_origin = CuisineOrigin.FRENCH
    recipe.origin_recipe = RecipeOrigin.PERSONAL
    recipe.course_type = CourseType.MAIN_COURSE
    recipe.prep_time_minutes = 15
    recipe.cook_time_minutes = 60
    recipe.servings = 4
    recipe.tags = {}
    recipe.book_name = None
    recipe.source_url = None
    recipe.image_url = None
    recipe.created_by_user_id = "123e4567-e89b-12d3-a456-426614174000"
    recipe.created_at = datetime(2026, 1, 1, 12, 0, 0)
    recipe.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    recipe.recipe_ingredients = recipe_ingredients or []
    return recipe


@pytest.fixture
def http_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")