from datetime import datetime
from unittest.mock import MagicMock

from app.services.import_task_service import ImportTaskService


def test_enqueue_sends_task_with_payload_and_notify_user():
    app = MagicMock()
    app.send_task.return_value = MagicMock(id="task-42")
    service = ImportTaskService(app)

    task_id = service.enqueue({"created_by_user_id": "u1", "recipes": []}, "admin-9")

    assert task_id == "task-42"
    app.send_task.assert_called_once_with(
        "app.tasks.import_task.import_recipes_payload",
        args=[{"created_by_user_id": "u1", "recipes": []}, "admin-9"],
    )


def test_enqueue_defaults_notify_user_to_none():
    app = MagicMock()
    app.send_task.return_value = MagicMock(id="task-1")
    ImportTaskService(app).enqueue({"recipes": []})

    _, kwargs = app.send_task.call_args
    assert kwargs["args"] == [{"recipes": []}, None]


def test_task_status_success_exposes_result():
    res = MagicMock()
    res.state = "SUCCESS"
    res.result = {"ingredients_upserted": 3, "recipes_created": 2, "recipe_slugs": []}
    res.ready.return_value = True
    res.successful.return_value = True
    res.date_done = datetime(2026, 6, 2, 10, 0, 0)
    app = MagicMock()
    app.AsyncResult.return_value = res

    status = ImportTaskService(app).task_status("task-42")

    assert status.task_id == "task-42"
    assert status.known is True
    assert status.ready is True
    assert status.successful is True
    assert status.error is None
    assert status.result["recipes_created"] == 2
    assert status.finished_at == "2026-06-02T10:00:00"


def test_task_status_failure_exposes_error():
    res = MagicMock()
    res.state = "FAILURE"
    res.result = ValueError("boom")
    res.ready.return_value = True
    res.successful.return_value = False
    res.date_done = None
    app = MagicMock()
    app.AsyncResult.return_value = res

    status = ImportTaskService(app).task_status("task-42")

    assert status.successful is False
    assert status.error == "boom"
    assert status.result is None
    assert status.finished_at is None


def test_task_status_pending_is_unknown():
    res = MagicMock()
    res.state = "PENDING"
    res.result = None
    res.ready.return_value = False
    res.date_done = None
    app = MagicMock()
    app.AsyncResult.return_value = res

    status = ImportTaskService(app).task_status("unknown-id")

    assert status.known is False
    assert status.ready is False
    assert status.successful is None
