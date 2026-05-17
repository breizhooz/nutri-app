import uuid
from datetime import time, timedelta
from unittest.mock import MagicMock

import pytest
from celery.schedules import crontab

from app.models.crawl_source import CrawlSource
from app.services.scheduler_service import SchedulerService


def _make_source(
    frequency_hours: int = 24,
    hour: int = 3,
    minute: int = 0,
    url: str = "@chef_instagram",
    source_id: uuid.UUID | None = None,
) -> CrawlSource:
    source = MagicMock(spec=CrawlSource)
    source.id = source_id or uuid.UUID("11111111-1111-1111-1111-111111111111")
    source.frequency_hours = frequency_hours
    source.execution_hour = time(hour, minute)
    source.url = url
    return source


class TestComputeSchedule:
    def test_24h_returns_daily_crontab(self):
        result = SchedulerService.compute_schedule(24, time(3, 0))
        assert isinstance(result, crontab)

    def test_24h_crontab_hour_correct(self):
        result = SchedulerService.compute_schedule(24, time(7, 0))
        assert result.hour == frozenset({7})

    def test_24h_crontab_minute_correct(self):
        result = SchedulerService.compute_schedule(24, time(3, 30))
        assert result.minute == frozenset({30})

    def test_24h_midnight(self):
        result = SchedulerService.compute_schedule(24, time(0, 0))
        assert isinstance(result, crontab)
        assert result.hour == frozenset({0})

    def test_12h_returns_timedelta(self):
        result = SchedulerService.compute_schedule(12, time(3, 0))
        assert isinstance(result, timedelta)
        assert result == timedelta(hours=12)

    def test_6h_returns_timedelta(self):
        assert SchedulerService.compute_schedule(6, time(0, 0)) == timedelta(hours=6)

    def test_48h_returns_timedelta(self):
        assert SchedulerService.compute_schedule(48, time(3, 0)) == timedelta(hours=48)

    def test_1h_returns_timedelta(self):
        assert SchedulerService.compute_schedule(1, time(0, 0)) == timedelta(hours=1)

    def test_non_24h_ignores_execution_hour(self):
        r1 = SchedulerService.compute_schedule(12, time(3, 0))
        r2 = SchedulerService.compute_schedule(12, time(9, 0))
        assert r1 == r2


class TestSourceKey:
    def test_key_format(self):
        sid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert SchedulerService.source_key(sid) == f"instagram_crawl_{sid}"

    def test_key_is_deterministic(self):
        sid = uuid.uuid4()
        assert SchedulerService.source_key(sid) == SchedulerService.source_key(sid)

    def test_different_ids_give_different_keys(self):
        assert SchedulerService.source_key(uuid.uuid4()) != SchedulerService.source_key(uuid.uuid4())


class TestBuildEntry:
    def test_has_required_keys(self):
        entry = SchedulerService.build_entry(_make_source())
        assert {"task", "schedule", "args", "options"} <= set(entry.keys())

    def test_task_name(self):
        entry = SchedulerService.build_entry(_make_source())
        assert entry["task"] == "tasks.instagram.crawl_instagram"

    def test_args_source_id(self):
        source = _make_source()
        entry = SchedulerService.build_entry(source)
        assert entry["args"][0] == str(source.id)

    def test_args_url(self):
        source = _make_source(url="@mon_compte")
        entry = SchedulerService.build_entry(source)
        assert entry["args"][1] == "@mon_compte"

    def test_options_expires_present(self):
        entry = SchedulerService.build_entry(_make_source())
        assert "expires" in entry["options"]

    def test_options_expires_value(self):
        entry = SchedulerService.build_entry(_make_source())
        assert entry["options"]["expires"] == SchedulerService.TASK_EXPIRES_SECONDS

    def test_24h_schedule_is_crontab(self):
        entry = SchedulerService.build_entry(_make_source(frequency_hours=24))
        assert isinstance(entry["schedule"], crontab)

    def test_12h_schedule_is_timedelta(self):
        entry = SchedulerService.build_entry(_make_source(frequency_hours=12))
        assert isinstance(entry["schedule"], timedelta)


class TestBuildSchedule:
    def test_empty_sources(self):
        assert SchedulerService.build_schedule([]) == {}

    def test_single_source_key_present(self):
        source = _make_source()
        schedule = SchedulerService.build_schedule([source])
        assert SchedulerService.source_key(source.id) in schedule

    def test_single_source_value_is_entry(self):
        source = _make_source()
        schedule = SchedulerService.build_schedule([source])
        entry = schedule[SchedulerService.source_key(source.id)]
        assert "task" in entry

    def test_multiple_sources_count(self):
        sources = [
            _make_source(source_id=uuid.UUID(f"1111111{i}-1111-1111-1111-111111111111"))
            for i in range(3)
        ]
        assert len(SchedulerService.build_schedule(sources)) == 3

    def test_multiple_sources_all_keys_present(self):
        sources = [
            _make_source(source_id=uuid.UUID(f"2222222{i}-2222-2222-2222-222222222222"))
            for i in range(3)
        ]
        schedule = SchedulerService.build_schedule(sources)
        for s in sources:
            assert SchedulerService.source_key(s.id) in schedule


class TestEntrySignature:
    def test_default_signature(self):
        source = _make_source(frequency_hours=24, hour=3, minute=0)
        assert SchedulerService.entry_signature(source) == (24, 3, 0)

    def test_custom_frequency(self):
        source = _make_source(frequency_hours=12, hour=3, minute=0)
        assert SchedulerService.entry_signature(source) == (12, 3, 0)

    def test_custom_hour(self):
        source = _make_source(frequency_hours=24, hour=9, minute=15)
        assert SchedulerService.entry_signature(source) == (24, 9, 15)

    def test_same_params_equal_signatures(self):
        s1 = _make_source(frequency_hours=24, hour=3, minute=0)
        s2 = _make_source(frequency_hours=24, hour=3, minute=0)
        assert SchedulerService.entry_signature(s1) == SchedulerService.entry_signature(s2)

    def test_different_frequency_different_sig(self):
        s1 = _make_source(frequency_hours=24, hour=3, minute=0)
        s2 = _make_source(frequency_hours=12, hour=3, minute=0)
        assert SchedulerService.entry_signature(s1) != SchedulerService.entry_signature(s2)

    def test_different_hour_different_sig(self):
        s1 = _make_source(frequency_hours=24, hour=3, minute=0)
        s2 = _make_source(frequency_hours=24, hour=9, minute=0)
        assert SchedulerService.entry_signature(s1) != SchedulerService.entry_signature(s2)

    def test_returns_tuple(self):
        result = SchedulerService.entry_signature(_make_source())
        assert isinstance(result, tuple)
        assert len(result) == 3