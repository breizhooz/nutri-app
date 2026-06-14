"""Application Celery du service-notification.

Porte les purges de rétention RGPD (art. 5.1.e, Phase 4) : suppression de
l'historique des notifications au-delà de la durée de conservation. Le worker
est lancé avec ``-B`` (beat embarqué) — cf. infra/compose/workers.yml.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "service-notification",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.retention"],
)

celery_app.conf.timezone = "Europe/Paris"

# Purges de rétention (RGPD art. 5.1.e) — Phase 4.
celery_app.conf.beat_schedule = {
    "purge-old-notifications": {
        "task": "retention.purge_old_notifications",
        "schedule": 86400.0,  # quotidien
    },
}
