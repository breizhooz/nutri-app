"""Tests unitaires — routes /api/v1/crawler/notifications."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_EXPO_TOKEN = "ExponentPushToken[test123]"
_WEB_TOKEN = '{"endpoint":"https://fcm.example.com","keys":{"p256dh":"k","auth":"a"}}'


def _mock_repo(upsert_return=None, delete_return=True):
    repo = AsyncMock()
    repo.upsert.return_value = upsert_return or MagicMock(id=uuid.uuid4())
    repo.delete_by_token.return_value = delete_return
    return repo


# ─── POST /subscribe ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_subscribe_expo_returns_201(client):
    with patch("app.api.routes.notifications.PushRepository", return_value=_mock_repo()):
        r = await client.post(
            "/api/v1/crawler/notifications",
            json={"channel": "expo", "token": _EXPO_TOKEN},
        )
    assert r.status_code == 201
    assert "message" in r.json()


@pytest.mark.anyio
async def test_subscribe_web_push_returns_201(client):
    with patch("app.api.routes.notifications.PushRepository", return_value=_mock_repo()):
        r = await client.post(
            "/api/v1/crawler/notifications",
            json={"channel": "web_push", "token": _WEB_TOKEN},
        )
    assert r.status_code == 201


@pytest.mark.anyio
async def test_subscribe_calls_upsert_with_correct_args(client):
    mock_repo = _mock_repo()
    with patch("app.api.routes.notifications.PushRepository", return_value=mock_repo):
        await client.post(
            "/api/v1/crawler/notifications",
            json={"channel": "expo", "token": _EXPO_TOKEN},
        )
    mock_repo.upsert.assert_called_once()
    call_kwargs = mock_repo.upsert.call_args
    assert call_kwargs.kwargs["token"] == _EXPO_TOKEN


@pytest.mark.anyio
async def test_subscribe_duplicate_still_returns_201(client):
    with patch("app.api.routes.notifications.PushRepository", return_value=_mock_repo()):
        r1 = await client.post(
            "/api/v1/crawler/notifications",
            json={"channel": "expo", "token": _EXPO_TOKEN},
        )
        r2 = await client.post(
            "/api/v1/crawler/notifications",
            json={"channel": "expo", "token": _EXPO_TOKEN},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.anyio
async def test_subscribe_missing_token_returns_422(client):
    r = await client.post(
        "/api/v1/crawler/notifications",
        json={"channel": "expo"},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_subscribe_empty_token_returns_422(client):
    r = await client.post(
        "/api/v1/crawler/notifications",
        json={"channel": "expo", "token": ""},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_subscribe_invalid_channel_returns_422(client):
    r = await client.post(
        "/api/v1/crawler/notifications",
        json={"channel": "sms", "token": "12345"},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_subscribe_missing_channel_returns_422(client):
    r = await client.post(
        "/api/v1/crawler/notifications",
        json={"token": _EXPO_TOKEN},
    )
    assert r.status_code == 422


# ─── DELETE /unsubscribe ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_unsubscribe_existing_returns_204(client):
    with patch("app.api.routes.notifications.PushRepository", return_value=_mock_repo(delete_return=True)):
        r = await client.request(
            "DELETE",
            "/api/v1/crawler/notifications",
            json={"token": _EXPO_TOKEN},
        )
    assert r.status_code == 204


@pytest.mark.anyio
async def test_unsubscribe_nonexistent_returns_204(client):
    """Suppression silencieuse même si le token est inconnu."""
    with patch("app.api.routes.notifications.PushRepository", return_value=_mock_repo(delete_return=False)):
        r = await client.request(
            "DELETE",
            "/api/v1/crawler/notifications",
            json={"token": "ghost-token"},
        )
    assert r.status_code == 204


@pytest.mark.anyio
async def test_unsubscribe_calls_delete_with_token(client):
    mock_repo = _mock_repo()
    with patch("app.api.routes.notifications.PushRepository", return_value=mock_repo):
        await client.request(
            "DELETE",
            "/api/v1/crawler/notifications",
            json={"token": _EXPO_TOKEN},
        )
    mock_repo.delete_by_token.assert_called_once()


@pytest.mark.anyio
async def test_unsubscribe_missing_token_returns_422(client):
    r = await client.request("DELETE", "/api/v1/crawler/notifications", json={})
    assert r.status_code == 422