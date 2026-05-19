from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery(
    "service-nutrition",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.ciqual_import"],
)

celery.conf.beat_schedule = {
    "ciqual-monthly-import": {
        "task": "tasks.ciqual_import.run",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),
    },
}