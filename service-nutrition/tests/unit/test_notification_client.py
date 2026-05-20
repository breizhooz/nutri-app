from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.notification_client import NotificationClient


class TestNotificationClient:
    @pytest.fixture
    def mock_http(self) -> AsyncMock:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
        return client

    @pytest.fixture
    def notif_client(self, mock_http) -> NotificationClient:
        return NotificationClient(http_client=mock_http)

    @pytest.mark.unit
    async def test_notify_macro_error_posts_correct_payload(self, notif_client, mock_http):
        """notify_macro_error() appelle POST /api/v1/notify avec le bon payload."""
        await notif_client.notify_macro_error(
            user_id="00000000-0000-0000-0000-000000000001",
            raw_ingredient="gochujank",
            macro_error_slug="gochujank-err",
        )
        mock_http.post.assert_called_once()
        call_kwargs = mock_http.post.call_args
        url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
        payload = call_kwargs[1]["json"]

        assert payload["type"] == "macro_error"
        assert "gochujank" in payload["body"]
        assert payload["data"]["macro_error_slug"] == "gochujank-err"

    @pytest.mark.unit
    async def test_notify_macro_error_http_error_not_raised(self, notif_client, mock_http):
        """HTTPError loguée, pas propagée."""
        mock_http.post = AsyncMock(
            side_effect=httpx.HTTPError("connection refused")
        )
        await notif_client.notify_macro_error(
            user_id="00000000-0000-0000-0000-000000000001",
            raw_ingredient="x",
            macro_error_slug="x-err",
        )

    @pytest.mark.unit
    async def test_notify_macro_error_user_id_in_payload(self, notif_client, mock_http):
        """user_slug du payload == user_id passé."""
        uid = "00000000-0000-0000-0000-000000000001"
        await notif_client.notify_macro_error(uid, "ing", "ing-err")
        payload = mock_http.post.call_args[1]["json"]
        assert payload["user_slug"] == uid