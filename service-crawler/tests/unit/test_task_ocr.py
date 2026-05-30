import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import CrawlType
from tasks.ocr import build_origin

_FAKE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_RAW_TEXT = "Tarte aux pommes\nIngrédients: pommes, farine, sucre"
_TITLE = "Tarte aux pommes"


def _make_session_ctx():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


def test_build_origin_is_deterministic():
    assert build_origin(_RAW_TEXT) == build_origin(_RAW_TEXT)
    assert build_origin(_RAW_TEXT).startswith("ocr://")
    assert build_origin("autre") != build_origin(_RAW_TEXT)


@pytest.mark.asyncio
async def test_do_process_nominal():
    fake_result = MagicMock()
    fake_result.id = uuid.uuid4()

    result_repo = AsyncMock()
    result_repo.user_link_exists = AsyncMock(return_value=False)
    result_repo.get_or_create_result = AsyncMock(return_value=(fake_result, True))
    result_repo.create_user_link = AsyncMock()

    mock_notif_client = AsyncMock()
    task = MagicMock()
    mock_session = _make_session_ctx()

    with (
        patch("tasks.ocr._make_session_factory") as mock_factory,
        patch("tasks.ocr.ResultRepository", return_value=result_repo),
        patch("tasks.ocr.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session

        from tasks.ocr import _do_process

        await _do_process(task, str(_FAKE_USER_ID), _RAW_TEXT, _TITLE)

    payload = result_repo.get_or_create_result.call_args[0][0]
    assert payload["type"] == CrawlType.OCR
    assert payload["title"] == _TITLE
    assert payload["raw_content"] == _RAW_TEXT
    assert payload["url_origin"] == build_origin(_RAW_TEXT)
    assert payload["images"] == []

    result_repo.create_user_link.assert_called_once_with(
        result_id=fake_result.id,
        user_id=_FAKE_USER_ID,
        source_id=None,
    )
    mock_notif_client.notify_crawl_done.assert_called_once_with(
        str(_FAKE_USER_ID), CrawlType.OCR.value, 1, "OCR"
    )


@pytest.mark.asyncio
async def test_do_process_skips_duplicate():
    result_repo = AsyncMock()
    result_repo.user_link_exists = AsyncMock(return_value=True)

    mock_notif_client = AsyncMock()
    task = MagicMock()
    mock_session = _make_session_ctx()

    with (
        patch("tasks.ocr._make_session_factory") as mock_factory,
        patch("tasks.ocr.ResultRepository", return_value=result_repo),
        patch("tasks.ocr.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session

        from tasks.ocr import _do_process

        await _do_process(task, str(_FAKE_USER_ID), _RAW_TEXT, _TITLE)

    result_repo.get_or_create_result.assert_not_called()
    result_repo.create_user_link.assert_not_called()
    mock_notif_client.notify_crawl_done.assert_not_called()


@pytest.mark.asyncio
async def test_do_process_retries_on_db_error():
    result_repo = AsyncMock()
    result_repo.user_link_exists = AsyncMock(return_value=False)
    result_repo.get_or_create_result = AsyncMock(side_effect=RuntimeError("db down"))

    mock_notif_client = AsyncMock()
    task = MagicMock()
    task.retry = MagicMock(side_effect=RuntimeError("retry called"))
    mock_session = _make_session_ctx()

    with (
        patch("tasks.ocr._make_session_factory") as mock_factory,
        patch("tasks.ocr.ResultRepository", return_value=result_repo),
        patch("tasks.ocr.NotificationClient", return_value=mock_notif_client),
    ):
        mock_factory.return_value.return_value = mock_session

        from tasks.ocr import _do_process

        with pytest.raises(RuntimeError, match="retry called"):
            await _do_process(task, str(_FAKE_USER_ID), _RAW_TEXT, _TITLE)

    task.retry.assert_called_once()
    mock_notif_client.notify_crawl_done.assert_not_called()
