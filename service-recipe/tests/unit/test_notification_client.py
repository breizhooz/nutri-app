import httpx
import pytest

from app.core.config import settings
from app.services.notification_client import NotificationClient


def _capturing_client(captured: list[dict]) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append({"url": str(request.url), "json": json.loads(request.content)})
        return httpx.Response(
            200, json={"slug": "n1", "status": "sent", "sent": 1, "failed": 0}
        )

    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://notif:8000"
    )


@pytest.fixture(autouse=True)
def _enable_notifications(monkeypatch):
    # _post court-circuite si l'URL est vide : on la renseigne pour les tests.
    monkeypatch.setattr(settings, "SERVICE_NOTIFICATION_URL", "http://notif:8000")
    yield


@pytest.mark.asyncio
async def test_notify_import_done_posts_system_notification():
    captured: list[dict] = []
    async with _capturing_client(captured) as http:
        await NotificationClient(http).notify_import_done(
            "user-1", recipes_created=3, ingredients_upserted=5
        )

    assert len(captured) == 1
    body = captured[0]["json"]
    assert body["user_slug"] == "user-1"
    assert body["type"] == "recipe_import_done"
    assert "3 recette" in body["body"]
    assert body["data"] == {"recipes_created": 3, "ingredients_upserted": 5}


@pytest.mark.asyncio
async def test_notify_import_error_posts_error_body():
    captured: list[dict] = []
    async with _capturing_client(captured) as http:
        await NotificationClient(http).notify_import_error("user-1", "boom")

    body = captured[0]["json"]
    assert body["type"] == "system"
    assert body["body"] == "boom"
    assert body["data"] is None


@pytest.mark.asyncio
async def test_notify_skipped_when_url_unset(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_NOTIFICATION_URL", "")
    captured: list[dict] = []
    # Même avec un client injecté, _post sort tôt si l'URL n'est pas configurée.
    async with _capturing_client(captured) as http:
        await NotificationClient(http).notify_import_done(
            "user-1", recipes_created=1, ingredients_upserted=1
        )
    assert captured == []


@pytest.mark.asyncio
async def test_notify_swallows_http_errors():
    async def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(failing), base_url="http://notif:8000"
    )
    async with http:
        # Ne doit pas lever : best-effort.
        await NotificationClient(http).notify_import_error("user-1", "boom")
