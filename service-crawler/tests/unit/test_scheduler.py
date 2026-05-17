import uuid
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scheduler_service import SchedulerService
from tasks.scheduler import DatabaseBackedScheduler, build_beat_schedule


def _make_source(
    freq: int = 24,
    hour: int = 3,
    minute: int = 0,
    url: str = "@account",
    source_id: uuid.UUID | None = None,
) -> MagicMock:
    source = MagicMock()
    source.id = source_id or uuid.uuid4()
    source.frequency_hours = freq
    source.execution_hour = time(hour, minute)
    source.url = url
    return source


def _make_scheduler() -> DatabaseBackedScheduler:
    scheduler = DatabaseBackedScheduler.__new__(DatabaseBackedScheduler)
    scheduler._entry_sigs = {}
    scheduler._last_db_poll = 0.0
    scheduler.data = {}
    scheduler.update_from_dict = MagicMock()
    return scheduler


# ── build_beat_schedule ────────────────────────────────────────────────────────

class TestBuildBeatSchedule:
    def test_returns_empty_dict_on_db_error(self):
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            side_effect=Exception("DB down"),
        ):
            result = build_beat_schedule()
        assert result == {}

    def test_returns_empty_dict_for_no_sources(self):
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = build_beat_schedule()
        assert result == {}

    def test_returns_entry_for_one_source(self):
        source = _make_source()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            result = build_beat_schedule()
        assert SchedulerService.source_key(source.id) in result

    def test_entry_has_correct_task(self):
        source = _make_source()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            result = build_beat_schedule()
        entry = result[SchedulerService.source_key(source.id)]
        assert entry["task"] == "tasks.instagram.crawl_instagram"

    def test_returns_entries_for_multiple_sources(self):
        sources = [_make_source() for _ in range(3)]
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=sources,
        ):
            result = build_beat_schedule()
        assert len(result) == 3

    def test_does_not_raise_on_exception(self):
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            side_effect=RuntimeError("crash"),
        ):
            result = build_beat_schedule()
        assert isinstance(result, dict)


# ── DatabaseBackedScheduler._sync_from_db ─────────────────────────────────────

class TestSyncFromDb:
    def test_adds_new_entry(self):
        source = _make_source()
        scheduler = _make_scheduler()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            scheduler._sync_from_db()
        scheduler.update_from_dict.assert_called_once()

    def test_new_entry_registered_in_sigs(self):
        source = _make_source(freq=24, hour=3, minute=0)
        scheduler = _make_scheduler()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            scheduler._sync_from_db()
        key = SchedulerService.source_key(source.id)
        assert key in scheduler._entry_sigs
        assert scheduler._entry_sigs[key] == (24, 3, 0)

    def test_removes_stale_entry(self):
        source_id = uuid.uuid4()
        key = SchedulerService.source_key(source_id)
        scheduler = _make_scheduler()
        scheduler.data = {key: MagicMock()}
        scheduler._entry_sigs = {key: (24, 3, 0)}
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            scheduler._sync_from_db()
        assert key not in scheduler.data
        assert key not in scheduler._entry_sigs

    def test_stale_entry_removed_from_data(self):
        sid = uuid.uuid4()
        key = SchedulerService.source_key(sid)
        scheduler = _make_scheduler()
        scheduler.data = {key: MagicMock()}
        scheduler._entry_sigs = {key: (24, 3, 0)}
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            scheduler._sync_from_db()
        assert key not in scheduler.data

    def test_skips_unchanged_entry(self):
        source = _make_source(freq=24, hour=3, minute=0)
        key = SchedulerService.source_key(source.id)
        scheduler = _make_scheduler()
        scheduler.data = {key: MagicMock()}
        scheduler._entry_sigs = {key: (24, 3, 0)}
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            scheduler._sync_from_db()
        scheduler.update_from_dict.assert_not_called()

    def test_updates_when_frequency_changed(self):
        source = _make_source(freq=12, hour=3, minute=0)
        key = SchedulerService.source_key(source.id)
        scheduler = _make_scheduler()
        scheduler.data = {key: MagicMock()}
        scheduler._entry_sigs = {key: (24, 3, 0)}
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            scheduler._sync_from_db()
        scheduler.update_from_dict.assert_called_once()
        assert scheduler._entry_sigs[key] == (12, 3, 0)

    def test_updates_when_hour_changed(self):
        source = _make_source(freq=24, hour=9, minute=0)
        key = SchedulerService.source_key(source.id)
        scheduler = _make_scheduler()
        scheduler.data = {key: MagicMock()}
        scheduler._entry_sigs = {key: (24, 3, 0)}
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[source],
        ):
            scheduler._sync_from_db()
        scheduler.update_from_dict.assert_called_once()

    def test_handles_db_error_gracefully(self):
        scheduler = _make_scheduler()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            side_effect=Exception("timeout"),
        ):
            scheduler._sync_from_db()
        scheduler.update_from_dict.assert_not_called()

    def test_updates_last_db_poll_on_success(self):
        scheduler = _make_scheduler()
        assert scheduler._last_db_poll == 0.0
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[],
        ):
            scheduler._sync_from_db()
        assert scheduler._last_db_poll > 0.0

    def test_updates_last_db_poll_on_error(self):
        scheduler = _make_scheduler()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            side_effect=Exception("fail"),
        ):
            scheduler._sync_from_db()
        assert scheduler._last_db_poll > 0.0

    def test_handles_multiple_new_sources(self):
        sources = [_make_source() for _ in range(4)]
        scheduler = _make_scheduler()
        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=sources,
        ):
            scheduler._sync_from_db()
        assert scheduler.update_from_dict.call_count == 4
        assert len(scheduler._entry_sigs) == 4

    def test_mixed_state_add_remove_skip(self):
        existing_id = uuid.uuid4()
        new_id      = uuid.uuid4()
        stale_id    = uuid.uuid4()

        existing_key = SchedulerService.source_key(existing_id)
        stale_key    = SchedulerService.source_key(stale_id)

        scheduler = _make_scheduler()
        scheduler.data = {existing_key: MagicMock(), stale_key: MagicMock()}
        scheduler._entry_sigs = {
            existing_key: (24, 3, 0),
            stale_key:    (24, 3, 0),
        }

        existing_source = _make_source(source_id=existing_id, freq=24, hour=3, minute=0)
        new_source      = _make_source(source_id=new_id)

        with patch(
            "tasks.scheduler._fetch_active_instagram_sources",
            new_callable=AsyncMock,
            return_value=[existing_source, new_source],
        ):
            scheduler._sync_from_db()

        assert stale_key not in scheduler.data
        assert existing_key in scheduler.data
        scheduler.update_from_dict.assert_called_once()