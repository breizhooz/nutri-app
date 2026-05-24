"""Tests for NotificationClient.send_mfa_code."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_client import NotificationClient

_COMMON_ARGS = ("user-id-123", "654321", "dest@test.com", "http://notif", "tok")


def _mock_httpx(status_code: int):
    """Build a patched httpx.AsyncClient returning a response with given status."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls


@pytest.mark.unit
async def test_send_mfa_code_200_returns_true() -> None:
    with patch("httpx.AsyncClient", _mock_httpx(200)):
        assert await NotificationClient.send_mfa_code(*_COMMON_ARGS) is True


@pytest.mark.unit
async def test_send_mfa_code_299_returns_true() -> None:
    with patch("httpx.AsyncClient", _mock_httpx(299)):
        assert await NotificationClient.send_mfa_code(*_COMMON_ARGS) is True


@pytest.mark.unit
async def test_send_mfa_code_400_returns_false() -> None:
    with patch("httpx.AsyncClient", _mock_httpx(400)):
        assert await NotificationClient.send_mfa_code(*_COMMON_ARGS) is False


@pytest.mark.unit
async def test_send_mfa_code_500_returns_false() -> None:
    with patch("httpx.AsyncClient", _mock_httpx(500)):
        assert await NotificationClient.send_mfa_code(*_COMMON_ARGS) is False


@pytest.mark.unit
async def test_send_mfa_code_network_error_returns_false() -> None:
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(
        side_effect=Exception("connection refused")
    )
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", mock_cls):
        assert await NotificationClient.send_mfa_code(*_COMMON_ARGS) is False


@pytest.mark.unit
async def test_send_mfa_code_sends_correct_payload() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", mock_cls):
        await NotificationClient.send_mfa_code(
            "uid-42", "999999", "a@b.com", "http://svc", "secret-tok"
        )

    call = mock_client.post.call_args
    assert call.kwargs["json"]["user_slug"] == "uid-42"
    assert call.kwargs["json"]["type"] == "mfa_code"
    assert call.kwargs["json"]["data"]["code"] == "999999"
    assert call.kwargs["headers"]["Authorization"] == "Bearer secret-tok"
    assert call.args[0] == "http://svc/api/v1/notify"
