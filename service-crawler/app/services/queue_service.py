"""Service de lecture de la file d'attente Celery via le protocole de contrôle.

Utilise ``celery_app.control.inspect()`` pour interroger les workers en direct
(tâches actives, planifiées/retries, réservées). Lecture seule, aucun effet de bord.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.schemas.queue import QueueSnapshot, QueueTask

logger = logging.getLogger(__name__)

# Timeout court : si aucun worker ne répond, inspect renvoie None (file vide).
# Chaque appel inspect() attend toute sa fenêtre → on les lance en parallèle.
_INSPECT_TIMEOUT_S = 1.0


class QueueService:
    """Construit un instantané de la file d'attente à partir des workers Celery."""

    def __init__(self, celery_app: Any = None) -> None:
        if celery_app is None:
            from celery_app import celery_app as default_app

            celery_app = default_app
        self._app = celery_app

    def _inspect(self, method: str):
        """Un appel inspect isolé (broadcast indépendant, exécutable en parallèle)."""
        inspector = self._app.control.inspect(timeout=_INSPECT_TIMEOUT_S)
        return getattr(inspector, method)()

    def snapshot(self) -> QueueSnapshot:
        """Retourne l'état courant de la file (bloquant : à exécuter hors event loop).

        Les 4 broadcasts inspect sont parallélisés pour rester sous ~1 s au lieu de ~Nx.
        """
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_ping = pool.submit(self._inspect, "ping")
            f_active = pool.submit(self._inspect, "active")
            f_scheduled = pool.submit(self._inspect, "scheduled")
            f_reserved = pool.submit(self._inspect, "reserved")
            ping = f_ping.result() or {}
            active = self._flatten(f_active.result())
            scheduled = self._flatten(f_scheduled.result(), scheduled=True)
            reserved = self._flatten(f_reserved.result())

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
