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
