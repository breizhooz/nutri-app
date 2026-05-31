"""Schémas de l'instantané de la file d'attente Celery (vue admin)."""

from typing import Any

from pydantic import BaseModel


class QueueTask(BaseModel):
    """Une tâche présente dans la file (active, planifiée ou réservée)."""

    id: str | None = None
    name: str | None = None
    args: Any = None
    kwargs: Any = None
    worker: str | None = None
    eta: str | None = None  # uniquement pour les tâches planifiées (retries)


class QueueSnapshot(BaseModel):
    """État instantané de la file d'attente, agrégé sur tous les workers."""

    workers: list[str]
    counts: dict[str, int]
    active: list[QueueTask]
    scheduled: list[QueueTask]
    reserved: list[QueueTask]


class TaskStatus(BaseModel):
    """Diagnostic d'une tâche Celery interrogée par son id (request id).

    ``state == "PENDING"`` (``known is False``) signifie que l'id est inconnu du
    backend OU que la tâche n'a pas encore démarré (Celery ne distingue pas).
    """

    task_id: str
    state: str
    known: bool
    ready: bool
    successful: bool | None = None
    error: str | None = None
    # date_done du backend : quand la tâche a terminé ou planté (ISO 8601).
    finished_at: str | None = None
