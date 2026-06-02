from celery import Celery

from app.schemas.recipe_import import ImportTaskStatus

_FAILED_STATES = {"FAILURE", "RETRY"}


class ImportTaskService:
    """Pilote l'import asynchrone : enfilement et lecture de l'état d'une tâche."""

    def __init__(self, celery_app: Celery) -> None:
        self._app = celery_app

    def enqueue(self, raw_payload: dict, notify_user_id: str | None = None) -> str:
        """Enfile l'import et retourne l'id de tâche (pour le polling du front).

        ``notify_user_id`` est l'admin déclencheur, notifié en fin/échec d'import.
        """
        task = self._app.send_task(
            "app.tasks.import_task.import_recipes_payload",
            args=[raw_payload, notify_user_id],
        )
        return task.id

    def task_status(self, task_id: str) -> ImportTaskStatus:
        """Interroge le result backend Celery pour l'état d'une tâche d'import.

        Lecture seule (bloquant : à exécuter hors event loop). Pour une tâche
        plantée (``FAILURE``/``RETRY``), ``error`` porte le message d'exception et
        ``finished_at`` la date du dernier échec.
        """
        res = self._app.AsyncResult(task_id)
        state = res.state
        info = res.result
        error = str(info) if state in _FAILED_STATES and info is not None else None
        result = info if state == "SUCCESS" and isinstance(info, dict) else None
        ready = res.ready()
        date_done = res.date_done
        return ImportTaskStatus(
            task_id=task_id,
            state=state,
            known=state != "PENDING",
            ready=ready,
            successful=res.successful() if ready else None,
            error=error,
            finished_at=date_done.isoformat() if date_done else None,
            result=result,
        )
