"""Tests unitaires — NotificationService."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pywebpush import WebPushException

from app.models.enums import PushChannel
from app.services.notification_service import (
    DispatchResult,
    NotificationPayload,
    NotificationService,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_service() -> NotificationService:
    return NotificationService(
        vapid_private_key="test-vapid-key",
        vapid_claims_email="test@example.com",
        expo_api_url="http://test-expo/push",
    )


def _make_sub(channel: PushChannel, token: str) -> MagicMock:
    sub = MagicMock()
    sub.user_id = uuid.uuid4()
    sub.channel = channel
    sub.token = token
    return sub


def _web_sub(token: str | None = None) -> MagicMock:
    return _make_sub(
        PushChannel.WEB_PUSH,
        token or json.dumps(
            {"endpoint": "https://fcm.example.com", "keys": {"p256dh": "k", "auth": "a"}}
        ),
    )


def _expo_sub(suffix: str = "test") -> MagicMock:
    return _make_sub(PushChannel.EXPO, f"ExponentPushToken[{suffix}]")


def _expo_response(status: str = "ok") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": [{"status": status, "message": "err"}]}
    return resp


def _mock_async_client(response: MagicMock) -> MagicMock:
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.return_value = response
    return client


# ─── build_payload ─────────────────────────────────────────────────────────────


def test_build_payload_uses_label_when_provided():
    payload = NotificationService.build_payload("instagram", 3, "chefmarco")
    assert "chefmarco" in payload.body
    assert "instagram" not in payload.body


def test_build_payload_falls_back_to_source_type():
    payload = NotificationService.build_payload("instagram", 3)
    assert "instagram" in payload.body


def test_build_payload_title_contains_brand():
    payload = NotificationService.build_payload("web", 1)
    assert "NutriPlanner" in payload.title


def test_build_payload_data_fields():
    payload = NotificationService.build_payload("instagram", 5, "chef")
    assert payload.data["source_type"] == "instagram"
    assert payload.data["new_count"] == 5


def test_build_payload_count_in_body():
    payload = NotificationService.build_payload("web", 42)
    assert "42" in payload.body


def test_build_payload_is_frozen_dataclass():
    payload = NotificationService.build_payload("web", 1)
    assert isinstance(payload, NotificationPayload)
    # frozen=True : toute affectation doit lever AttributeError
    import pytest as _pytest
    with _pytest.raises((AttributeError, TypeError)):
        payload.title = "new"  # type: ignore[misc]


# ─── dispatch ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dispatch_empty_returns_zeros():
    result = await _make_service().dispatch([], NotificationService.build_payload("web", 1))
    assert result.sent == 0 and result.failed == 0


@pytest.mark.anyio
async def test_dispatch_all_success():
    service = _make_service()
    subs = [_expo_sub("1"), _expo_sub("2")]
    with patch.object(service, "_send_expo", AsyncMock(return_value=True)):
        result = await service.dispatch(subs, NotificationService.build_payload("web", 1))
    assert result.sent == 2 and result.failed == 0


@pytest.mark.anyio
async def test_dispatch_all_failed():
    service = _make_service()
    subs = [_expo_sub("1"), _expo_sub("2")]
    with patch.object(service, "_send_expo", AsyncMock(return_value=False)):
        result = await service.dispatch(subs, NotificationService.build_payload("web", 1))
    assert result.sent == 0 and result.failed == 2


@pytest.mark.anyio
async def test_dispatch_mixed():
    service = _make_service()
    subs = [_expo_sub(str(i)) for i in range(4)]
    with patch.object(service, "_send_expo", AsyncMock(side_effect=[True, False, True, False])):
        result = await service.dispatch(subs, NotificationService.build_payload("web", 1))
    assert result.sent == 2 and result.failed == 2


@pytest.mark.anyio
async def test_dispatch_routes_to_web_push():
    service = _make_service()
    with patch.object(service, "_send_web_push", AsyncMock(return_value=True)) as wp, \
         patch.object(service, "_send_expo", AsyncMock(return_value=True)) as ex:
        await service.dispatch([_web_sub()], NotificationService.build_payload("web", 1))
    wp.assert_called_once()
    ex.assert_not_called()


@pytest.mark.anyio
async def test_dispatch_routes_to_expo():
    service = _make_service()
    with patch.object(service, "_send_web_push", AsyncMock(return_value=True)) as wp, \
         patch.object(service, "_send_expo", AsyncMock(return_value=True)) as ex:
        await service.dispatch([_expo_sub()], NotificationService.build_payload("web", 1))
    ex.assert_called_once()
    wp.assert_not_called()


# ─── _route — canal inconnu ────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_route_unknown_channel_returns_false():
    sub = _make_sub("fax", "token")  # type: ignore[arg-type]
    result = await _make_service()._route(sub, NotificationService.build_payload("web", 1))
    assert result is False


# ─── _send_web_push ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_send_web_push_success():
    with patch("app.services.notification_service.asyncio.to_thread", AsyncMock(return_value=None)):
        result = await _make_service()._send_web_push(
            _web_sub(), NotificationService.build_payload("web", 1)
        )
    assert result is True


@pytest.mark.anyio
async def test_send_web_push_invalid_json():
    result = await _make_service()._send_web_push(
        _make_sub(PushChannel.WEB_PUSH, "NOT_JSON{{{"),
        NotificationService.build_payload("web", 1),
    )
    assert result is False


@pytest.mark.anyio
async def test_send_web_push_vapid_exception():
    with patch(
        "app.services.notification_service.asyncio.to_thread",
        AsyncMock(side_effect=WebPushException("401")),
    ):
        result = await _make_service()._send_web_push(
            _web_sub(), NotificationService.build_payload("web", 1)
        )
    assert result is False


@pytest.mark.anyio
async def test_send_web_push_unexpected_exception():
    with patch(
        "app.services.notification_service.asyncio.to_thread",
        AsyncMock(side_effect=RuntimeError("connection reset")),
    ):
        result = await _make_service()._send_web_push(
            _web_sub(), NotificationService.build_payload("web", 1)
        )
    assert result is False


# ─── _send_expo ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_send_expo_success():
    with patch(
        "app.services.notification_service.httpx.AsyncClient",
        return_value=_mock_async_client(_expo_response("ok")),
    ):
        result = await _make_service()._send_expo(
            _expo_sub(), NotificationService.build_payload("instagram", 2)
        )
    assert result is True


@pytest.mark.anyio
async def test_send_expo_api_error_status():
    with patch(
        "app.services.notification_service.httpx.AsyncClient",
        return_value=_mock_async_client(_expo_response("error")),
    ):
        result = await _make_service()._send_expo(
            _expo_sub(), NotificationService.build_payload("instagram", 1)
        )
    assert result is False


@pytest.mark.anyio
async def test_send_expo_http_error():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.side_effect = httpx.ConnectError("refused")
    with patch("app.services.notification_service.httpx.AsyncClient", return_value=client):
        result = await _make_service()._send_expo(
            _expo_sub(), NotificationService.build_payload("instagram", 1)
        )
    assert result is False


@pytest.mark.anyio
async def test_send_expo_empty_tickets_returns_true():
    """data:[] → ticket absent → pas d'erreur détectée → True (raise_for_status déjà passé)."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": []}
    with patch(
        "app.services.notification_service.httpx.AsyncClient",
        return_value=_mock_async_client(resp),
    ):
        result = await _make_service()._send_expo(
            _expo_sub(), NotificationService.build_payload("web", 1)
        )
    assert result is True