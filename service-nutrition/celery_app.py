from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "service-nutrition",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.nutrition_task"],
)

celery_app.conf.timezone = "Europe/Paris"
celery_app.conf.beat_schedule = {
    "import-ciqual-monthly": {
        "task": "app.tasks.nutrition_tasks.import_ciqual",
        "schedule": 2_592_000,
    },
    "enrich-off-daily": {
        "task": "app.tasks.nutrition_tasks.enrich_from_off",
        "schedule": 86_400,
    },
}