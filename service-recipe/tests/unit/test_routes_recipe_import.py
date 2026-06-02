import json

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.api.routes.recipes import ImportTaskServiceFactory
from app.core.deps import require_admin
from app.core.http_client import get_user_client, ServiceUnavailableError
from app.main import app
from app.schemas.recipe_import import ImportTaskStatus


def _override_admin():
    app.dependency_overrides[require_admin] = lambda: {
        "sub": "admin-1",
        "type": "access",
        "user_admin": True,
    }


def _override_user_client(*, exists: bool = True, unavailable: bool = False):
    """Stub service-user : par défaut le created_by_user_id existe."""
    client = MagicMock()
    if unavailable:
        client.user_exist = AsyncMock(side_effect=ServiceUnavailableError("down"))
    else:
        client.user_exist = AsyncMock(return_value=exists)
    app.dependency_overrides[get_user_client] = lambda: client
    return client


def _upload(content: str):
    return {"file": ("recipes.json", content.encode("utf-8"), "application/json")}


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_valid_payload_enqueues_task():
    _override_admin()
    user_client = _override_user_client(exists=True)
    mock_service = MagicMock()
    mock_service.enqueue.return_value = "task-123"
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

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

    assert response.status_code == 202
    assert response.json() == {"task_id": "task-123", "status": "queued"}
    user_client.user_exist.assert_awaited_once_with(payload["created_by_user_id"])
    mock_service.enqueue.assert_called_once()
    # Le worker reçoit le payload re-sérialisé JSON-safe + l'id de l'admin déclencheur.
    sent_payload, notify_user_id = mock_service.enqueue.call_args.args
    assert sent_payload["created_by_user_id"] == payload["created_by_user_id"]
    assert notify_user_id == "admin-1"


@pytest.mark.asyncio
async def test_import_unknown_user_returns_422_without_enqueue():
    _override_admin()
    _override_user_client(exists=False)
    mock_service = MagicMock()
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

    payload = {
        "created_by_user_id": "a3f1c2d4-5678-90ab-cdef-1234567890ab",
        "recipes": [],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload(json.dumps(payload))
        )

    assert response.status_code == 422
    mock_service.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_import_service_user_unavailable_returns_503_without_enqueue():
    _override_admin()
    _override_user_client(unavailable=True)
    mock_service = MagicMock()
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

    payload = {
        "created_by_user_id": "00000000-0000-0000-0000-000000000000",
        "recipes": [],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload(json.dumps(payload))
        )

    assert response.status_code == 503
    mock_service.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_import_invalid_json_returns_400_without_enqueue():
    _override_admin()
    mock_service = MagicMock()
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload("{ not json")
        )

    assert response.status_code == 400
    mock_service.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_import_validation_error_returns_400_without_enqueue():
    _override_admin()
    mock_service = MagicMock()
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

    # Missing required created_by_user_id → pydantic ValidationError.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/recipe/import", files=_upload(json.dumps({"recipes": []}))
        )

    assert response.status_code == 400
    mock_service.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_import_status_returns_task_state():
    _override_admin()
    mock_service = MagicMock()
    mock_service.task_status.return_value = ImportTaskStatus(
        task_id="task-123",
        state="SUCCESS",
        known=True,
        ready=True,
        successful=True,
        error=None,
        finished_at="2026-06-02T10:00:00",
        result={"ingredients_upserted": 2, "recipes_created": 1, "recipe_slugs": ["x"]},
    )
    app.dependency_overrides[ImportTaskServiceFactory.inject] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recipe/import/task-123")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-123"
    assert body["successful"] is True
    assert body["result"]["recipes_created"] == 1
    mock_service.task_status.assert_called_once_with("task-123")
