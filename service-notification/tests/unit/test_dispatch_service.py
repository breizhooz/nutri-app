import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import NotificationStatus, NotificationType
from app.services.dispatch_service import DispatchResult, DispatchService
from app.services.push_service import PushService


def _make_push(send_result: bool = True) -> PushService:
    mock = MagicMock(spec=PushService)
    mock.send = AsyncMock(return_value=send_result)
    return mock


def _make_notif(slug: str = "notif-slug") -> MagicMock:
    n = MagicMock()
    n.slug = slug
    n.status = NotificationStatus.PENDING
    return n


def _patch_repos(subscriptions, notif):
    """Patche SubscriptionRepository et NotificationRepository dans dispatch_service."""
    sub_patch = patch("app.services.dispatch_service.SubscriptionRepository")
    notif_patch = patch("app.services.dispatch_service.NotificationRepository")
    return sub_patch, notif_patch, subscriptions, notif


class TestDispatchService:
    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        return uuid.UUID("00000000-0000-0000-0000-000000000001")

    @pytest.fixture
    def sub(self, user_id):
        s = MagicMock()
        s.user_id = user_id
        s.slug = "test-sub"
        return s

    @pytest.mark.unit
    async def test_dispatch_one_device_success(self, db_session, user_id, sub):
        """1 device abonné, envoi réussi → sent=1, failed=0, status=sent."""
        notif = _make_notif()
        notif.status = NotificationStatus.SENT
        push = _make_push(send_result=True)

        with patch("app.services.dispatch_service.SubscriptionRepository") as SR, \
             patch("app.services.dispatch_service.NotificationRepository") as NR:
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
        self, db_session, user_id
    ):
        """0 devices → sent=0, failed=0, status=failed (notification créée en base)."""
        notif = _make_notif()
        notif.status = NotificationStatus.FAILED
        push = _make_push()

        with patch("app.services.dispatch_service.SubscriptionRepository") as SR, \
             patch("app.services.dispatch_service.NotificationRepository") as NR:
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
        assert result.failed == 0
        assert result.status == NotificationStatus.FAILED

    @pytest.mark.unit
    async def test_dispatch_partial_failure(self, db_session, user_id):
        """2 devices, 1 réussit → sent=1, failed=1, status=sent (au moins 1 envoyé)."""
        sub1, sub2 = MagicMock(), MagicMock()
        notif = _make_notif()
        notif.status = NotificationStatus.SENT
        push = MagicMock(spec=PushService)
        push.send = AsyncMock(side_effect=[True, False])

        with patch("app.services.dispatch_service.SubscriptionRepository") as SR, \
             patch("app.services.dispatch_service.NotificationRepository") as NR:
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
    async def test_dispatch_all_devices_fail(self, db_session, user_id, sub):
        """Tous les envois échouent → status=failed."""
        notif = _make_notif()
        notif.status = NotificationStatus.FAILED
        push = _make_push(send_result=False)

        with patch("app.services.dispatch_service.SubscriptionRepository") as SR, \
             patch("app.services.dispatch_service.NotificationRepository") as NR:
            SR.return_value.get_by_user_id = AsyncMock(return_value=[sub])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id, type=NotificationType.MACRO_ERROR,
                title="T", body="B",
            )

        assert result.sent == 0
        assert result.failed == 1
        assert result.status == NotificationStatus.FAILED

    @pytest.mark.unit
    async def test_dispatch_creates_notification_before_sending(
        self, db_session, user_id, sub
    ):
        """La notification est créée en base avant l'envoi (pour le tracking)."""
        notif = _make_notif("notif-abc")
        notif.status = NotificationStatus.SENT
        push = _make_push()

        with patch("app.services.dispatch_service.SubscriptionRepository") as SR, \
             patch("app.services.dispatch_service.NotificationRepository") as NR:
            SR.return_value.get_by_user_id = AsyncMock(return_value=[sub])
            NR.return_value.create = AsyncMock(return_value=notif)
            NR.return_value.update_status = AsyncMock(return_value=notif)

            result = await DispatchService(db_session, push).dispatch(
                user_id=user_id, type=NotificationType.SYSTEM,
                title="T", body="B", data={"key": "val"},
            )

            NR.return_value.create.assert_called_once()
            assert result.notification_slug == "notif-abc"