from celery import Celery

from app.core.config import settings
from nutri_shared.core.logger import configure_logging

configure_logging("service-recipe-worker")

celery_app = Celery(
    "service-recipe",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.import_task"],
)

# Queue dédiée "recipe" : le broker Redis est partagé entre services, on évite
# ainsi que le worker d'un autre service (qui écoute la queue par défaut "celery")
# tente de consommer — et fasse échouer — nos tâches.
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="recipe",
    task_routes={"app.tasks.import_task.*": {"queue": "recipe"}},
)
