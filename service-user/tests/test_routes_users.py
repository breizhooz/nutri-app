import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.session import get_session
from app.models.user import User

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
async def test_check_user_exists(override_db):

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "1234-1234"
    override_db.execute.return_value = mock_result

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/1234-1234/exists")

    assert response.status_code == 200
    assert response.json() == {"exists": True}

@pytest.mark.asyncio
async def test_check_user_doesnt_exists(override_db):

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/1234-1234/exists")

    assert response.status_code == 200
    assert response.json() == {"exists": False}