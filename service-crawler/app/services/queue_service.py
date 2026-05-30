"""Service de lecture de la file d'attente Celery via le protocole de contrôle.

Utilise ``celery_app.control.inspect()`` pour interroger les workers en direct
(tâches actives, planifiées/retries, réservées). Lecture seule, aucun effet de bord.
"""

import logging
from typing import Any

from app.schemas.queue import QueueSnapshot, QueueTask

logger = logging.getLogger(__name__)

# Timeout court : si aucun worker ne répond, inspect renvoie None (file vide).
_INSPECT_TIMEOUT_S = 1.5


class QueueService:
    """Construit un instantané de la file d'attente à partir des workers Celery."""

    def __init__(self, celery_app: Any = None) -> None:
        if celery_app is None:
            from celery_app import celery_app as default_app

            celery_app = default_app
        self._app = celery_app

    def snapshot(self) -> QueueSnapshot:
        """Retourne l'état courant de la file (bloquant : à exécuter hors event loop)."""
        inspector = self._app.control.inspect(timeout=_INSPECT_TIMEOUT_S)

        ping = inspector.ping() or {}
        active = self._flatten(inspector.active())
        scheduled = self._flatten(inspector.scheduled(), scheduled=True)
        reserved = self._flatten(inspector.reserved())

        workers = sorted(ping.keys())
        return QueueSnapshot(
            workers=workers,
            counts={
                "workers": len(workers),
                "active": len(active),
                "scheduled": len(scheduled),
                "reserved": len(reserved),
            },
            active=active,
            scheduled=scheduled,
            reserved=reserved,
        )

    @staticmethod
    def _flatten(
        by_worker: dict[str, list[dict]] | None, scheduled: bool = False
    ) -> list[QueueTask]:
        """Aplati la sortie ``{worker: [tâches]}`` d'inspect en liste de QueueTask.

        Les tâches planifiées encapsulent leurs infos dans ``request`` et portent un ``eta``.
        """
        out: list[QueueTask] = []
        for worker, tasks in (by_worker or {}).items():
            for t in tasks or []:
                req = t.get("request", t) if scheduled else t
                out.append(
                    QueueTask(
                        id=req.get("id"),
                        name=req.get("name"),
                        args=req.get("args"),
                        kwargs=req.get("kwargs"),
                        worker=worker,
                        eta=t.get("eta") if scheduled else None,
                    )
                )
        return out
