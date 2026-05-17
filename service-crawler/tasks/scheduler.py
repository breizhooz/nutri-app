"""
Phase 7 — Scheduler configurable.

DatabaseBackedScheduler : sous-classe de PersistentScheduler qui synchronise
le planning Celery Beat avec la table crawl_sources (PostgreSQL) toutes les
_DB_POLL_INTERVAL secondes.

Comportement :
- Ajout     : nouvelles sources actives → entrées ajoutées sans restart.
- Suppression : sources désactivées/supprimées → entrées retirées.
- Mise à jour : frequency_hours ou execution_hour modifiés → entrée rechargée.
  Les sources inchangées conservent leur last_run_at.

Démarrage (docker-compose) :
    celery -A celery_app beat -l info
beat_scheduler est configuré dans celery_app.conf.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from celery.beat import PersistentScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.crawl_source import CrawlSource
from app.models.enums import CrawlType
from app.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

# Fréquence de relecture de la DB par le processus beat.
_DB_POLL_INTERVAL: float = 60.0


async def _fetch_active_instagram_sources() -> list[CrawlSource]:
    """
    Requête PostgreSQL : toutes les sources Instagram actives.
    Crée un engine jetable pour que le processus beat reste indépendant.
    """
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                select(CrawlSource).where(
                    CrawlSource.actif == True,  # noqa: E712
                    CrawlSource.type == CrawlType.INSTAGRAM,
                )
            )
            return list(result.scalars().all())
    finally:
        await engine.dispose()


def build_beat_schedule() -> dict[str, Any]:
    """
    Construit le planning Beat complet depuis la DB.
    Retourne {} si la DB est inaccessible — DatabaseBackedScheduler
    prendra le relais dès son démarrage.
    """
    try:
        sources = asyncio.run(_fetch_active_instagram_sources())
        schedule = SchedulerService.build_schedule(sources)
        logger.info("Beat schedule initialisé : %d source(s) Instagram", len(schedule))
        return schedule
    except Exception as exc:
        logger.warning("Beat schedule build échoué (DB inaccessible ?) : %s", exc)
        return {}


class DatabaseBackedScheduler(PersistentScheduler):
    """
    Scheduler Celery Beat piloté par la table crawl_sources.

    Toutes les _DB_POLL_INTERVAL secondes, _sync_from_db() réconcilie
    l'état en mémoire avec la DB :
    - Entrées devenues inactives → supprimées.
    - Nouvelles sources actives  → ajoutées.
    - Schedule modifié           → entrée mise à jour (last_run_at réinitialisé,
                                    compromis acceptable).
    - Sources inchangées         → ignorées (last_run_at préservé).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Initialisé AVANT super().__init__() car setup_schedule() est appelé
        # à l'intérieur de super().__init__() et utilise ces attributs.
        self._entry_sigs: dict[str, tuple[int, int, int]] = {}
        self._last_db_poll: float = 0.0
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        """Appelé une fois au démarrage : charge l'état persisté puis synchro DB."""
        super().setup_schedule()
        self._sync_from_db()

    def tick(self, event_t: Any = ..., **kwargs: Any) -> float:
        """Appelé à chaque itération de la boucle beat."""
        if time.monotonic() - self._last_db_poll >= _DB_POLL_INTERVAL:
            self._sync_from_db()
        return super().tick(event_t, **kwargs)

    # ------------------------------------------------------------------
    # Privé
    # ------------------------------------------------------------------

    def _sync_from_db(self) -> None:
        """Recharge le planning depuis la DB et réconcilie l'état en mémoire."""
        try:
            sources = asyncio.run(_fetch_active_instagram_sources())
        except Exception as exc:
            logger.error("Beat : sync DB échoué : %s", exc)
            self._last_db_poll = time.monotonic()
            return

        desired_entries: dict[str, dict[str, Any]] = {}
        desired_sigs: dict[str, tuple[int, int, int]] = {}
        for s in sources:
            key = SchedulerService.source_key(s.id)
            desired_entries[key] = SchedulerService.build_entry(s)
            desired_sigs[key] = SchedulerService.entry_signature(s)

        current_keys = set(self.data.keys())
        desired_keys = set(desired_entries.keys())

        # Supprimer les sources désactivées ou retirées.
        for key in current_keys - desired_keys:
            del self.data[key]
            self._entry_sigs.pop(key, None)
            logger.info("Beat : entrée supprimée — %s", key)

        # Ajouter les nouvelles entrées ; mettre à jour uniquement si le schedule a changé.
        for key in desired_keys:
            entry_dict = desired_entries[key]
            new_sig = desired_sigs[key]

            if key not in current_keys:
                self.update_from_dict({key: entry_dict})
                self._entry_sigs[key] = new_sig
                logger.info("Beat : entrée ajoutée — %s", key)

            elif self._entry_sigs.get(key) != new_sig:
                old_sig = self._entry_sigs.get(key)
                self.update_from_dict({key: entry_dict})
                self._entry_sigs[key] = new_sig
                logger.info("Beat : schedule mis à jour — %s (%s → %s)", key, old_sig, new_sig)

        self._last_db_poll = time.monotonic()
        logger.info("Beat : sync terminé — %d source(s) Instagram active(s)", len(sources))