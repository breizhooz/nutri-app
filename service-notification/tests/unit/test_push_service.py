import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from pywebpush import WebPushException

from app.models.subscription import Subscription
from app.services.push_service import PushService


def _make_sub(**overrides) -> Subscription:
    sub = MagicMock(spec=Subscription)
    sub.id = uuid.uuid4()
    sub.slug = "test-device-slug"
    sub.user_id = uuid.uuid4()
    sub.endpoint = "https://fcm.googleapis.com/fcm/send/abc123"
    sub.p256dh_key = "BNcTestP256dhKey"
    sub.auth_key = "TestAuthKey"
    sub.device_label = "Chrome Desktop"
    for k, v in overrides.items():
        setattr(sub, k, v)
    return sub


class TestPushService:
    @pytest.fixture
    def svc(self) -> PushService:
        return PushService(
            vapid_private_key="test-vapid-key",
            vapid_claims_email="admin@nutriplanner.app",
        )

    @pytest.fixture
    def sub(self) -> Subscription:
        return _make_sub()

    @pytest.mark.unit
    async def test_send_success_returns_true(self, svc, sub):
        """Envoi réussi → True."""
        with patch("app.services.push_service.webpush", return_value=None):
            assert await svc.send(sub, "Titre", "Corps") is True

    @pytest.mark.unit
    async def test_send_webpush_exception_returns_false(self, svc, sub):
        """WebPushException (device injoignable / 410 Gone) → False sans lever."""
        with patch(
            "app.services.push_service.webpush",
            side_effect=WebPushException("gone"),
        ):
            assert await svc.send(sub, "T", "B") is False

    @pytest.mark.unit
    async def test_send_unexpected_exception_returns_false(self, svc, sub):
        """Exception inattendue → False, pas de propagation."""
        with patch(
            "app.services.push_service.webpush",
            side_effect=RuntimeError("network crash"),
        ):
            assert await svc.send(sub, "T", "B") is False

    @pytest.mark.unit
    async def test_send_passes_correct_subscription_info(self, svc, sub):
        """Les clés p256dh et auth sont transmises telles quelles à pywebpush."""
        with patch("app.services.push_service.webpush", return_value=None) as mock_wp:
            await svc.send(sub, "T", "B")
        info = mock_wp.call_args[1]["subscription_info"]
        assert info["endpoint"] == sub.endpoint
        assert info["keys"]["p256dh"] == sub.p256dh_key
        assert info["keys"]["auth"] == sub.auth_key

    @pytest.mark.unit
    async def test_send_includes_data_in_json_payload(self, svc, sub):
        """Le champ data est sérialisé dans le payload JSON."""
        with patch("app.services.push_service.webpush", return_value=None) as mock_wp:
            await svc.send(sub, "T", "B", data={"macro_error_slug": "gochujank-20260518"})
        raw = mock_wp.call_args[1]["data"]
        parsed = json.loads(raw)
        assert parsed["data"]["macro_error_slug"] == "gochujank-20260518"
        assert parsed["title"] == "T"
        assert parsed["body"] == "B"

    @pytest.mark.unit
    async def test_send_uses_correct_vapid_claims(self, svc, sub):
        """Le claim VAPID `sub` contient l'email configuré."""
        with patch("app.services.push_service.webpush", return_value=None) as mock_wp:
            await svc.send(sub, "T", "B")
        claims = mock_wp.call_args[1]["vapid_claims"]
        assert claims["sub"] == "mailto:admin@nutriplanner.app"
    
    @pytest.mark.unit
    async def test_send_with_no_data_uses_empty_dict(self, svc, sub):
        """data=None → payload JSON contient data={}."""
        import json
        with patch("app.services.push_service.webpush", return_value=None) as mock_wp:
            await svc.send(sub, "T", "B", data=None)
        raw = mock_wp.call_args[1]["data"]
        assert json.loads(raw)["data"] == {}