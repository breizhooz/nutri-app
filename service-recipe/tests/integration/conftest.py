import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from nutri_shared.core.context import AccessContext

from app.main import app
from app.db.session import get_session
from app.core.http_client import get_user_client
from app.core.deps import (
    get_current_user_id,
    get_read_account_id,
    get_read_context,
    get_write_account_id,
    get_write_auth,
    get_write_context,
    WriteAuth,
)
from app.models.enums import CuisineOrigin, CourseType, DifficultyLevel, RecipeOrigin

TEST_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
TEST_ACCOUNT_ID = "acc-123e4567-e89b-12d3-a456-426614174000"


def _test_ctx() -> AccessContext:
    return AccessContext(
        sub=TEST_USER_ID,
        account_id=TEST_ACCOUNT_ID,
        scopes=frozenset({"recipe:read", "recipe:write"}),
        user_admin=False,
        capabilities={},
    )


@pytest.fixture(autouse=True)
def override_current_user():
    overrides = {
        get_current_user_id: lambda: TEST_USER_ID,
        get_read_account_id: lambda: TEST_ACCOUNT_ID,
        get_write_account_id: lambda: TEST_ACCOUNT_ID,
        get_read_context: _test_ctx,
        get_write_context: _test_ctx,
        get_write_auth: lambda: WriteAuth(
            trusted=False, account_id=TEST_ACCOUNT_ID, sub=TEST_USER_ID
        ),
    }
    app.dependency_overrides.update(overrides)
    yield
    for dep in overrides:
        app.dependency_overrides.pop(dep, None)


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
        mock.search = AsyncMock(
            return_value={"hits": {"total": {"value": 0}, "hits": []}}
        )
        yield mock


def make_mock_recipe(
    recipe_id=1, title="Poulet rôti", slug="poulet-roti", recipe_ingredients=None
):
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
    recipe.free_tags = []
    recipe.book_name = None
    recipe.source_url = None
    recipe.image_url = None
    recipe.image_thumb_url = None
    recipe.image_suggestions = []
    recipe.image_search_keyword = None
    recipe.created_by_user_id = "123e4567-e89b-12d3-a456-426614174000"
    recipe.account_id = TEST_ACCOUNT_ID
    recipe.source_recipe_id = None
    recipe.created_at = datetime(2026, 1, 1, 12, 0, 0)
    recipe.updated_at = datetime(2026, 1, 1, 12, 0, 0)
    recipe.calories_per_serving = 520.0
    recipe.proteins_per_serving = 42.0
    recipe.carbs_per_serving = 30.0
    recipe.fats_per_serving = 18.0
    recipe.comment = None
    recipe.rating = None
    recipe.recipe_ingredients = recipe_ingredients or []
    return recipe


@pytest.fixture
def http_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
