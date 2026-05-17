"""Tests unitaires — tâche Celery send_crawl_notification."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tasks.notifications import _do_notify


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_sub():
    sub = MagicMock()
    sub.user_id = uuid.uuid4()
    return sub


def _build_factory():
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None
    factory = MagicMock(return_value=cm)
    return factory


def _patched_settings(vapid_key: str = "vapid-key"):
    mock = MagicMock()
    mock.VAPID_PRIVATE_KEY = vapid_key
    mock.VAPID_CLAIMS_EMAIL = "admin@test.com"
    mock.EXPO_PUSH_API_URL = "http://expo-test"
    return mock


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_no_vapid_key_exits_without_db_access():
    mock_repo = AsyncMock()
    with patch("tasks.notifications.settings", _patched_settings(vapid_key="")), \
         patch("tasks.notifications._make_session_factory", return_value=_build_factory()), \
         patch("tasks.notifications.PushRepository", return_value=mock_repo):
        await _do_notify(MagicMock(), str(uuid.uuid4()), "instagram", 3, "@chef")
    mock_repo.get_by_user_id.assert_not_called()


@pytest.mark.anyio
async def test_no_subscriptions_skips_dispatch():
    mock_repo = AsyncMock()
    mock_repo.get_by_user_id.return_value = []
    mock_svc_cls = MagicMock()

    with patch("tasks.notifications.settings", _patched_settings()), \
         patch("tasks.notifications._make_session_factory", return_value=_build_factory()), \
         patch("tasks.notifications.PushRepository", return_value=mock_repo), \
         patch("tasks.notifications.NotificationService", mock_svc_cls):
        await _do_notify(MagicMock(), str(uuid.uuid4()), "instagram", 2, "")

    # NotificationService doit être instancié mais dispatch ne doit pas être appelé
    mock_svc_cls.return_value.dispatch.assert_not_called()


@pytest.mark.anyio
async def test_dispatches_when_subscriptions_exist():
    user_id = uuid.uuid4()
    subs = [_make_sub(), _make_sub()]

    mock_repo = AsyncMock()
    mock_repo.get_by_user_id.return_value = subs

    mock_svc_instance = AsyncMock()
    mock_svc_instance.dispatch.return_value = MagicMock(sent=2, failed=0)
    mock_svc_cls = MagicMock(return_value=mock_svc_instance)
    mock_svc_cls.build_payload = MagicMock(return_value=MagicMock())

    with patch("tasks.notifications.settings", _patched_settings()), \
         patch("tasks.notifications._make_session_factory", return_value=_build_factory()), \
         patch("tasks.notifications.PushRepository", return_value=mock_repo), \
         patch("tasks.notifications.NotificationService", mock_svc_cls):
        await _do_notify(MagicMock(), str(user_id), "instagram", 3, "@chef")

    mock_repo.get_by_user_id.assert_called_once_with(user_id)
    mock_svc_instance.dispatch.assert_called_once()


@pytest.mark.anyio
async def test_build_payload_called_with_correct_args():
    user_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.get_by_user_id.return_value = [_make_sub()]

    mock_svc_instance = AsyncMock()
    mock_svc_instance.dispatch.return_value = MagicMock(sent=1, failed=0)
    mock_svc_cls = MagicMock(return_value=mock_svc_instance)
    mock_svc_cls.build_payload = MagicMock(return_value=MagicMock())

    with patch("tasks.notifications.settings", _patched_settings()), \
         patch("tasks.notifications._make_session_factory", return_value=_build_factory()), \
         patch("tasks.notifications.PushRepository", return_value=mock_repo), \
         patch("tasks.notifications.NotificationService", mock_svc_cls):
        await _do_notify(MagicMock(), str(user_id), "web", 5, "https://example.com")

    mock_svc_cls.build_payload.assert_called_once_with("web", 5, "https://example.com")


@pytest.mark.anyio
async def test_service_instantiated_with_vapid_config():
    user_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.get_by_user_id.return_value = [_make_sub()]

    mock_svc_instance = AsyncMock()
    mock_svc_instance.dispatch.return_value = MagicMock(sent=1, failed=0)
    mock_svc_cls = MagicMock(return_value=mock_svc_instance)
    mock_svc_cls.build_payload = MagicMock(return_value=MagicMock())

    settings = _patched_settings("my-vapid-key")

    with patch("tasks.notifications.settings", settings), \
         patch("tasks.notifications._make_session_factory", return_value=_build_factory()), \
         patch("tasks.notifications.PushRepository", return_value=mock_repo), \
         patch("tasks.notifications.NotificationService", mock_svc_cls):
        await _do_notify(MagicMock(), str(user_id), "instagram", 1, "")

    mock_svc_cls.assert_called_once_with(
        vapid_private_key="my-vapid-key",
        vapid_claims_email="admin@test.com",
        expo_api_url="http://expo-test",
    )