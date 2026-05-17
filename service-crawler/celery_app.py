from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "service-crawler",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.web",
        "tasks.instagram",
        "tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_scheduler="tasks.scheduler:DatabaseBackedScheduler",
    beat_max_loop_interval=5,
)