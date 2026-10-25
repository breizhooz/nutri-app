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

# File dédiée (comme recipe/crawler) : sans elle, les tâches partaient dans la
# file par défaut « celery », partagée avec d'autres services dont les workers
# jetaient les tâches inconnues (ex. purges RGPD, effacement de compte).
# Le worker compose écoute cette file (-Q notification) ; le beat y envoie aussi.
celery_app.conf.task_default_queue = "notification"

# Purges de rétention (RGPD art. 5.1.e) — Phase 4.
celery_app.conf.beat_schedule = {
    "purge-old-notifications": {
        "task": "retention.purge_old_notifications",
        "schedule": 86400.0,  # quotidien
    },
}
