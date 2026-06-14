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
    include=["app.tasks.erasure", "app.tasks.retention"],
)

celery_app.conf.timezone = "Europe/Paris"

# Purges de rétention (RGPD art. 5.1.e) — Phase 4. Exécutées par le worker
# lancé avec ``-B`` (beat embarqué).
celery_app.conf.beat_schedule = {
    "purge-expired-auth-tokens": {
        "task": "retention.purge_expired_auth_tokens",
        "schedule": 3600.0,  # toutes les heures
    },
    "purge-stale-invitations": {
        "task": "retention.purge_stale_invitations",
        "schedule": 86400.0,  # quotidien
    },
    "purge-old-audit-logs": {
        "task": "retention.purge_old_audit_logs",
        "schedule": 86400.0,  # quotidien
    },
    "purge-inactive-accounts": {
        "task": "retention.purge_inactive_accounts",
        "schedule": 86400.0,  # quotidien — comptes inactifs > 24 mois
    },
}
