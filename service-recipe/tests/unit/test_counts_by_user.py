from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.deps import require_admin
from app.services.recipe_service import RecipeService


@pytest.mark.asyncio
async def test_counts_by_user_maps_repo_rows_to_dict():
    repo = AsyncMock()
    repo.count_by_user.return_value = [("user-a", 3), ("user-b", 1)]
    service = RecipeService(repo, AsyncMock())

    result = await service.counts_by_user()

    assert result == {"user-a": 3, "user-b": 1}
    repo.count_by_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_counts_by_user_empty():
    repo = AsyncMock()
    repo.count_by_user.return_value = []
    service = RecipeService(repo, AsyncMock())

    assert await service.counts_by_user() == {}


@pytest.mark.asyncio
async def test_require_admin_allows_admin_claim():
    payload = {"sub": "u1", "type": "access", "user_admin": True}
    assert await require_admin(payload) is payload


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as exc:
        await require_admin({"sub": "u1", "type": "access", "user_admin": False})
    assert exc.value.status_code == 403
