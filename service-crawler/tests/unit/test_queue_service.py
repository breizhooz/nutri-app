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
