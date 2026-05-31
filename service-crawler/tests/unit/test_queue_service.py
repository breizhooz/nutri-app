from datetime import datetime
from unittest.mock import MagicMock

from app.services.queue_service import QueueService


def _inspector(active=None, scheduled=None, reserved=None, ping=None):
    insp = MagicMock()
    insp.ping.return_value = ping
    insp.active.return_value = active
    insp.scheduled.return_value = scheduled
    insp.reserved.return_value = reserved
    return insp


def _app_with(inspector):
    app = MagicMock()
    app.control.inspect.return_value = inspector
    return app


class TestQueueService:
    def test_empty_when_no_workers(self):
        app = _app_with(_inspector())  # tout None → aucun worker ne répond
        snap = QueueService(celery_app=app).snapshot()
        assert snap.workers == []
        assert snap.counts == {
            "workers": 0,
            "active": 0,
            "scheduled": 0,
            "reserved": 0,
        }
        assert snap.active == []

    def test_flattens_active_and_scheduled(self):
        insp = _inspector(
            ping={"w1": {"ok": "pong"}},
            active={
                "w1": [
                    {
                        "id": "a1",
                        "name": "tasks.instagram.crawl_instagram",
                        "args": ["swiss.fitcook"],
                        "kwargs": {},
                    }
                ]
            },
            scheduled={
                "w1": [
                    {
                        "eta": "2026-05-30T19:00:00+02:00",
                        "request": {
                            "id": "s1",
                            "name": "tasks.instagram.crawl_instagram",
                            "args": [],
                            "kwargs": {},
                        },
                    }
                ]
            },
            reserved={},
        )
        snap = QueueService(celery_app=_app_with(insp)).snapshot()

        assert snap.workers == ["w1"]
        assert snap.counts["active"] == 1
        assert snap.counts["scheduled"] == 1
        assert snap.active[0].id == "a1"
        assert snap.active[0].name == "tasks.instagram.crawl_instagram"
        assert snap.active[0].args == ["swiss.fitcook"]
        assert snap.active[0].worker == "w1"
        # la tâche planifiée (retry) : id depuis request, eta présent
        assert snap.scheduled[0].id == "s1"
        assert snap.scheduled[0].eta == "2026-05-30T19:00:00+02:00"


def _app_with_result(result) -> MagicMock:
    app = MagicMock()
    app.AsyncResult.return_value = result
    return app


class TestTaskStatus:
    def test_retry_reports_error_and_failure_time(self):
        res = MagicMock()
        res.state = "RETRY"
        res.result = Exception("Instagram rate limit")
        res.ready.return_value = False
        res.date_done = datetime(2026, 5, 30, 18, 0, 0)

        status = QueueService(celery_app=_app_with_result(res)).task_status("s1")

        assert status.task_id == "s1"
        assert status.state == "RETRY"
        assert status.known is True
        assert status.ready is False
        assert status.successful is None
        assert status.error == "Instagram rate limit"
        assert status.finished_at == "2026-05-30T18:00:00"

    def test_failure_reports_error(self):
        res = MagicMock()
        res.state = "FAILURE"
        res.result = Exception("boom")
        res.ready.return_value = True
        res.successful.return_value = False
        res.date_done = datetime(2026, 5, 30, 18, 0, 0)

        status = QueueService(celery_app=_app_with_result(res)).task_status("f1")

        assert status.state == "FAILURE"
        assert status.ready is True
        assert status.successful is False
        assert status.error == "boom"

    def test_success_has_no_error(self):
        res = MagicMock()
        res.state = "SUCCESS"
        res.result = {"new": 3}
        res.ready.return_value = True
        res.successful.return_value = True
        res.date_done = datetime(2026, 5, 30, 18, 0, 0)

        status = QueueService(celery_app=_app_with_result(res)).task_status("ok1")

        assert status.state == "SUCCESS"
        assert status.successful is True
        assert status.error is None

    def test_pending_is_unknown(self):
        res = MagicMock()
        res.state = "PENDING"
        res.result = None
        res.ready.return_value = False
        res.date_done = None

        status = QueueService(celery_app=_app_with_result(res)).task_status("nope")

        assert status.known is False
        assert status.error is None
        assert status.finished_at is None
