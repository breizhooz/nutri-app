"""Unit tests for DispatchService and email dispatch via notify route."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import NotificationStatus, NotificationType
from app.services.dispatch_service import DispatchService
from app.services.push_service import PushService


def _make_push(send_result: bool = True) -> PushService:
    """Create a mock PushService."""
    mock = MagicMock(spec=PushService)
    mock.send = AsyncMock(return_value=send_result)
    return mock


def _make_notif(slug: str = "notif-slug") -> MagicMock:
    """Create a mock Notification object."""
    n = MagicMock()
    n.slug = slug
    n.status = NotificationStatus.PENDING
    return n


class TestDispatchService:
    """Tests for DispatchService push dispatch."""

    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        """Return a fixed test user UUID."""
        return uuid.UUID("00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def sub(self, user_id: uuid.UUID) -> MagicMock:
        """Return a mock subscription object."""
        s = MagicMock()
        s.user_id = user_id
        s.slug = "test-sub"
        return s

    @pytest.mark.unit
    async def test_dispatch_one_device_success(
        self, db_session, user_id: uuid.UUID, sub: MagicMock
    ) -> None:
        """1 device abonné, envoi réussi → sent=1, failed=0, status=sent."""
        notif = _make_notif()
        notif.status = NotificationStatus.SENT
        push = _make_push(send_result=True)

        with (
            patch("app.services.dispatch_service.SubscriptionRepository") as SR,
            patch("app.services.dispatch_service.NotificationRepository") as NR,
        ):
            SR.return_value.get_by_user_id = AsyncMock(return_value=[sub])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id,
                type=NotificationType.MACRO_ERROR,
                title="Ingrédient non reconnu",
                body="Gochujank introuvable",
            )

        assert result.sent == 1
        assert result.failed == 0
        assert result.status == NotificationStatus.SENT

    @pytest.mark.unit
    async def test_dispatch_no_subscriptions_creates_failed_notification(
        self, db_session, user_id: uuid.UUID
    ) -> None:
        """0 devices → sent=0, failed=0, status=failed."""
        notif = _make_notif()
        notif.status = NotificationStatus.FAILED
        push = _make_push()

        with (
            patch("app.services.dispatch_service.SubscriptionRepository") as SR,
            patch("app.services.dispatch_service.NotificationRepository") as NR,
        ):
            SR.return_value.get_by_user_id = AsyncMock(return_value=[])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id,
                type=NotificationType.SYSTEM,
                title="Test",
                body="No devices",
            )

        assert result.sent == 0
        assert result.status == NotificationStatus.FAILED

    @pytest.mark.unit
    async def test_dispatch_partial_failure(
        self, db_session, user_id: uuid.UUID
    ) -> None:
        """2 devices, 1 réussit → sent=1, failed=1, status=sent."""
        sub1, sub2 = MagicMock(), MagicMock()
        notif = _make_notif()
        notif.status = NotificationStatus.SENT
        push = MagicMock(spec=PushService)
        push.send = AsyncMock(side_effect=[True, False])

        with (
            patch("app.services.dispatch_service.SubscriptionRepository") as SR,
            patch("app.services.dispatch_service.NotificationRepository") as NR,
        ):
            SR.return_value.get_by_user_id = AsyncMock(return_value=[sub1, sub2])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id,
                type=NotificationType.CRAWL_DONE,
                title="Crawl terminé",
                body="5 recettes disponibles",
            )

        assert result.sent == 1
        assert result.failed == 1
        assert result.status == NotificationStatus.SENT

    @pytest.mark.unit
    async def test_dispatch_all_devices_fail(
        self, db_session, user_id: uuid.UUID, sub: MagicMock
    ) -> None:
        """Tous les envois échouent → status=failed."""
        notif = _make_notif()
        notif.status = NotificationStatus.FAILED
        push = _make_push(send_result=False)

        with (
            patch("app.services.dispatch_service.SubscriptionRepository") as SR,
            patch("app.services.dispatch_service.NotificationRepository") as NR,
        ):
            SR.return_value.get_by_user_id = AsyncMock(return_value=[sub])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id,
                type=NotificationType.MACRO_ERROR,
                title="T",
                body="B",
            )

        assert result.sent == 0
        assert result.failed == 1
        assert result.status == NotificationStatus.FAILED


class TestNotifyRouteMfaCode:
    """Tests for MFA_CODE dispatch via the /api/v1/notify route."""

    @pytest.mark.unit
    async def test_mfa_code_email_sent_successfully(self, service_client) -> None:
        """POST /notify with mfa_code type calls EmailService and returns sent=1."""
        with patch(
            "app.api.routes.notify.EmailService.send_mfa_code",
            new=AsyncMock(return_value=True),
        ):
            resp = await service_client.post(
                "/api/v1/notify",
                json={
                    "user_slug": "00000000-0000-0000-0000-000000000001",
                    "type": "mfa_code",
                    "title": "Code 2FA",
                    "body": "Votre code : 123456",
                    "data": {"code": "123456"},
                    "recipient_email": "user@test.com",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sent"] == 1
        assert body["failed"] == 0
        assert body["status"] == "sent"

    @pytest.mark.unit
    async def test_mfa_code_without_recipient_email_returns_422(
        self, service_client
    ) -> None:
        """POST /notify with mfa_code but no recipient_email returns 422."""
        resp = await service_client.post(
            "/api/v1/notify",
            json={
                "user_slug": "00000000-0000-0000-0000-000000000001",
                "type": "mfa_code",
                "title": "Code",
                "body": "Code",
                "data": {"code": "123456"},
            },
        )
        assert resp.status_code == 422

    @pytest.mark.unit
    async def test_mfa_code_email_failure_returns_failed_status(
        self, service_client
    ) -> None:
        """POST /notify with mfa_code returns failed status when email send fails."""
        with patch(
            "app.api.routes.notify.EmailService.send_mfa_code",
            new=AsyncMock(return_value=False),
        ):
            resp = await service_client.post(
                "/api/v1/notify",
                json={
                    "user_slug": "00000000-0000-0000-0000-000000000001",
                    "type": "mfa_code",
                    "title": "Code",
                    "body": "Code",
                    "data": {"code": "123456"},
                    "recipient_email": "user@test.com",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["failed"] == 1
