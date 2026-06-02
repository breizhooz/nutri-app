import json

import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport

from app.api.routes.recipes import RecipeImportServiceFactory
from app.core.deps import require_admin
from app.main import app
from app.services.recipe_import_service import ImportReport


def _override_admin():
    app.dependency_overrides[require_admin] = lambda: {
        "sub": "admin-1",
        "type": "access",
        "user_admin": True,
    }


def _upload(content: str):
    return {"file": ("recipes.json", content.encode("utf-8"), "application/json")}


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_valid_payload_returns_report():
    _override_admin()
    mock_service = AsyncMock()
    mock_service.import_payload.return_value = ImportReport(
        ingredients_upserted=2, recipes_created=1, recipe_slugs=["risotto"]
    )
    app.dependency_overrides[RecipeImportServiceFactory.inject] = lambda: mock_service

    payload = {
        "created_by_user_id": "00000000-0000-0000-0000-000000000000",
        "ingredients": [
            {"name": "riz", "calories_per_100g": 350.0},
        ],
        "recipes": [],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload(json.dumps(payload))
        )

    assert response.status_code == 201
    assert response.json() == {
        "ingredients_upserted": 2,
        "recipes_created": 1,
        "recipe_slugs": ["risotto"],
    }
    mock_service.import_payload.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_invalid_json_returns_400():
    _override_admin()
    app.dependency_overrides[RecipeImportServiceFactory.inject] = lambda: AsyncMock()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload("{ not json")
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_import_validation_error_returns_400():
    _override_admin()
    mock_service = AsyncMock()
    app.dependency_overrides[RecipeImportServiceFactory.inject] = lambda: mock_service

    # Missing required created_by_user_id → pydantic ValidationError.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload(json.dumps({"recipes": []}))
        )

    assert response.status_code == 400
    mock_service.import_payload.assert_not_awaited()
