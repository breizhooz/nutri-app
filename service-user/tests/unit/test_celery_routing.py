"""Routage Celery : toutes les tâches de service-user partent dans SA file.

Régression évitée : sans file dédiée, les tâches allaient dans la file par
défaut « celery », partagée avec d'autres services dont les workers jetaient
les tâches inconnues (purges RGPD, effacement de compte…).
"""

import pytest

from celery_app import celery_app

QUEUE = "user"


def _queue_of(task_name: str, options: dict | None = None) -> str:
    return celery_app.amqp.router.route(options or {}, task_name)["queue"].name


@pytest.mark.unit
def test_default_queue_is_dedicated():
    assert celery_app.conf.task_default_queue == QUEUE


@pytest.mark.unit
def test_beat_tasks_are_routed_to_dedicated_queue():
    schedule = celery_app.conf.beat_schedule
    assert schedule, "aucune tâche planifiée : test à revoir"
    for entry in schedule.values():
        assert _queue_of(entry["task"], entry.get("options")) == QUEUE, entry["task"]


@pytest.mark.unit
def test_registered_tasks_are_routed_to_dedicated_queue():
    celery_app.loader.import_default_modules()
    own = [name for name in celery_app.tasks if not name.startswith("celery.")]
    assert own, "aucune tâche enregistrée : test à revoir"
    for name in own:
        assert _queue_of(name) == QUEUE, name
