"""Application Celery du service-user.

Porte l'orchestration asynchrone de l'effacement RGPD (art. 17) : à la
suppression d'un compte, une tâche purge les données de l'utilisateur dans les
autres microservices, avec reprise sur échec partiel via le journal
``erasure_targets``.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "service-user",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.erasure"],
)

celery_app.conf.timezone = "Europe/Paris"
