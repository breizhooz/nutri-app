import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.enums import CrawlType, CrawlStatus

_FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_FAKE_SOURCE_ID = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
_FAKE_URL = "https://example.com/recipe"


def _make_fake_source():
    source = MagicMock()
    source.id = uuid.UUID(_FAKE_SOURCE_ID)
    source.user_id = _FAKE_USER_ID
    source.url = _FAKE_URL
    source.type = CrawlType.WEB
    return source


def _make_session_ctx():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.mark.asyncio
async def test_do_crawl_nominal():
    fake_source = _make_fake_source()
    fake_data = {
        "title": "Tarte aux pommes",
        "raw_content": "Ingrédients: pommes, farine...",
        "images": ["https://example.com/img.jpg"],
        "video_url": None,
    }

    result_repo = AsyncMock()
    result_repo.url_exists = AsyncMock(return_value=False)
    result_repo.create = AsyncMock()

    source_repo = AsyncMock()
    source_repo.get_by_id = AsyncMock(return_value=fake_source)
    source_repo.mark_crawled = AsyncMock()

    mock_notif_client = AsyncMock()
    task = MagicMock()
    mock_session = _make_session_ctx()

    with (
        patch("tasks.web._make_session_factory") as mock_factory,
        patch("tasks.web.ResultRepository", return_value=result_repo),
        patch("tasks.web.SourceRepository", return_value=source_repo),
        patch("tasks.web.WebService") as mock_ws_cls,
        patch("tasks.web.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session
        mock_ws = AsyncMock()
        mock_ws.fetch = AsyncMock(return_value=fake_data)
        mock_ws_cls.return_value = mock_ws

        from tasks.web import _do_crawl
        await _do_crawl(task, _FAKE_SOURCE_ID, _FAKE_URL)

    result_repo.url_exists.assert_called_once_with(_FAKE_URL)
    result_repo.create.assert_called_once()

    payload = result_repo.create.call_args[0][0]
    assert payload["title"] == "Tarte aux pommes"
    assert payload["status"] == CrawlStatus.WAITING
    assert payload["type"] == CrawlType.WEB
    assert payload["user_id"] == _FAKE_USER_ID
    assert payload["source_id"] == uuid.UUID(_FAKE_SOURCE_ID)

    source_repo.mark_crawled.assert_called_once_with(fake_source)
    mock_notif_client.notify_crawl_done.assert_called_once_with(
        str(_FAKE_USER_ID), CrawlType.WEB.value, 1, _FAKE_URL
    )


@pytest.mark.asyncio
async def test_do_crawl_skips_duplicate_url():
    result_repo = AsyncMock()
    result_repo.url_exists = AsyncMock(return_value=True)
    source_repo = AsyncMock()
    mock_notif_client = AsyncMock()
    task = MagicMock()
    mock_session = _make_session_ctx()

    with (
        patch("tasks.web._make_session_factory") as mock_factory,
        patch("tasks.web.ResultRepository", return_value=result_repo),
        patch("tasks.web.SourceRepository", return_value=source_repo),
        patch("tasks.web.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session

        from tasks.web import _do_crawl
        await _do_crawl(task, _FAKE_SOURCE_ID, _FAKE_URL)

    result_repo.create.assert_not_called()
    source_repo.mark_crawled.assert_not_called()
    mock_notif_client.notify_crawl_done.assert_not_called()


@pytest.mark.asyncio
async def test_do_crawl_retries_on_fetch_error():
    result_repo = AsyncMock()
    result_repo.url_exists = AsyncMock(return_value=False)

    source_repo = AsyncMock()
    source_repo.get_by_id = AsyncMock(return_value=_make_fake_source())

    mock_notif_client = AsyncMock()
    task = MagicMock()
    task.retry = MagicMock(side_effect=RuntimeError("retry called"))
    mock_session = _make_session_ctx()

    with (
        patch("tasks.web._make_session_factory") as mock_factory,
        patch("tasks.web.ResultRepository", return_value=result_repo),
        patch("tasks.web.SourceRepository", return_value=source_repo),
        patch("tasks.web.WebService") as mock_ws_cls,
        patch("tasks.web.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session
        mock_ws = AsyncMock()
        mock_ws.fetch = AsyncMock(side_effect=ConnectionError("network failure"))
        mock_ws_cls.return_value = mock_ws

        from tasks.web import _do_crawl
        with pytest.raises(RuntimeError, match="retry called"):
            await _do_crawl(task, _FAKE_SOURCE_ID, _FAKE_URL)

    task.retry.assert_called_once()
    result_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_do_crawl_no_source_id():
    fake_data = {"title": "Recette ponctuelle", "raw_content": "...", "images": [], "video_url": None}

    result_repo = AsyncMock()
    result_repo.url_exists = AsyncMock(return_value=False)
    result_repo.create = AsyncMock()

    source_repo = AsyncMock()
    mock_notif_client = AsyncMock()
    task = MagicMock()
    mock_session = _make_session_ctx()

    with (
        patch("tasks.web._make_session_factory") as mock_factory,
        patch("tasks.web.ResultRepository", return_value=result_repo),
        patch("tasks.web.SourceRepository", return_value=source_repo),
        patch("tasks.web.WebService") as mock_ws_cls,
        patch("tasks.web.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session
        mock_ws = AsyncMock()
        mock_ws.fetch = AsyncMock(return_value=fake_data)
        mock_ws_cls.return_value = mock_ws

        from tasks.web import _do_crawl
        await _do_crawl(task, None, _FAKE_URL)

    payload = result_repo.create.call_args[0][0]
    assert payload["source_id"] is None
    assert payload["user_id"] is None

    source_repo.get_by_id.assert_not_called()
    source_repo.mark_crawled.assert_not_called()
    mock_notif_client.notify_crawl_done.assert_not_called()