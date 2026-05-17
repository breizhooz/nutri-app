from __future__ import annotations

import uuid
from datetime import time, timedelta
from typing import Any

from celery.schedules import crontab

from app.models.crawl_source import CrawlSource


class SchedulerService:
    """
    Logique métier pure pour construire des entrées Celery Beat à partir
    des CrawlSource.  Aucun accès DB — entièrement testable sans infrastructure.
    """

    INSTAGRAM_TASK = "tasks.instagram.crawl_instagram"
    TASK_EXPIRES_SECONDS = 3600

    @staticmethod
    def source_key(source_id: uuid.UUID) -> str:
        """Clé stable dans le planning Beat pour une source donnée."""
        return f"instagram_crawl_{source_id}"

    @staticmethod
    def compute_schedule(frequency_hours: int, execution_hour: time) -> crontab | timedelta:
        """
        Retourne l'objet schedule Celery adapté :
        - 24 h  → crontab quotidien à execution_hour (heure et minute exactes)
        - autre → timedelta(hours=frequency_hours)
        """
        if frequency_hours == 24:
            return crontab(hour=execution_hour.hour, minute=execution_hour.minute)
        return timedelta(hours=frequency_hours)

    @classmethod
    def build_entry(cls, source: CrawlSource) -> dict[str, Any]:
        """Convertit un CrawlSource en dict d'entrée Celery Beat."""
        return {
            "task": cls.INSTAGRAM_TASK,
            "schedule": cls.compute_schedule(source.frequency_hours, source.execution_hour),
            "args": [str(source.id), source.url],
            "options": {"expires": cls.TASK_EXPIRES_SECONDS},
        }

    @classmethod
    def build_schedule(cls, sources: list[CrawlSource]) -> dict[str, dict[str, Any]]:
        """Construit le planning Beat complet depuis une liste de sources actives."""
        return {
            cls.source_key(source.id): cls.build_entry(source)
            for source in sources
        }

    @staticmethod
    def entry_signature(source: CrawlSource) -> tuple[int, int, int]:
        """
        Empreinte compacte des paramètres de planification d'une source.
        Utilisée pour détecter les changements sans réécrire inutilement les entrées.
        """
        return (
            source.frequency_hours,
            source.execution_hour.hour,
            source.execution_hour.minute,
        )