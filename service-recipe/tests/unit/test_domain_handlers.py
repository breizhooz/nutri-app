"""The domain-exception handlers translate service errors into localized
HTTP responses ({"error": {"code", "message"}}) — see app/core/error_handlers.

The handlers are route-agnostic, so we drive each mapping through a single
read endpoint whose service call is mocked to raise the domain exception.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes.ingredient import IngredientServiceFactory
from app.api.routes.recipes import RecipeServiceFactory
from app.core.deps import get_read_account_id
from app.core.exceptions import (
    IngredientAlreadyExists,
    IngredientNotFound,
    RecipeForbidden,
    RecipeNotFound,
    SlugGenerationError,
)
from app.main import app


async def _get(path: str) -> tuple[int, dict]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(path)
    return response.status_code, response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc, expected_status, expected_code",
    [
        (RecipeNotFound(), 404, "RECIPE_NOT_FOUND"),
        (RecipeForbidden(), 403, "RECIPE_UNAUTHORIZED"),
        (SlugGenerationError(), 422, "RECIPE_SLUG_TOO_BIG"),
    ],
)
async def test_recipe_domain_errors_are_localized(exc, expected_status, expected_code):
    service = AsyncMock()
    service.get_by_id.side_effect = exc
    app.dependency_overrides[RecipeServiceFactory.inject] = lambda: service
    app.dependency_overrides[get_read_account_id] = lambda: "acc-1"
    try:
        status_code, body = await _get("/api/v1/recipe/id/1")
    finally:
        app.dependency_overrides.clear()

    assert status_code == expected_status
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"]  # localized, non-empty


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc, expected_status, expected_code",
    [
        (IngredientNotFound(), 404, "INGREDIENT_NOT_FOUND"),
        (IngredientAlreadyExists(), 409, "INGREDIENT_ALREADY_EXISTS"),
    ],
)
async def test_ingredient_domain_errors_are_localized(
    exc, expected_status, expected_code
):
    service = AsyncMock()
    service.get.side_effect = exc
    app.dependency_overrides[IngredientServiceFactory.inject] = lambda: service
    try:
        status_code, body = await _get("/api/v1/ingredient/1")
    finally:
        app.dependency_overrides.clear()

    assert status_code == expected_status
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"]
