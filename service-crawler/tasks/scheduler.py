from celery_app import celery_app


def build_beat_schedule() -> dict:
    """
    Construit le planning Celery Beat depuis la DB.
    Appelé au démarrage de celery-beat pour charger les sources actives.
    Implémenté en Phase 7.
    """
    return {}


celery_app.conf.beat_schedule = build_beat_schedule()