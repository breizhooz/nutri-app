"""Orchestration de l'effacement RGPD (art. 17) cross-service.

``request_erasure`` enregistre le journal (une cible par service) et trace
l'intention dans ``audit_logs``. ``process_erasure_request`` exécute la purge,
idempotente et rejouable. ``schedule_erasure`` programme la tâche Celery.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import AuditLog
from app.repositories.erasure_repository import ErasureRepository
from app.services.erasure_client import ERASURE_SERVICES, ErasureClient

logger = logging.getLogger(__name__)


async def request_erasure(
    session: AsyncSession,
    user_id: uuid.UUID | None,
    account_ids: list[uuid.UUID],
) -> uuid.UUID:
    """Crée le journal d'effacement (une cible par service) + trace l'audit.

    Retourne le ``request_id`` à confier à la tâche Celery.
    """
    request_id = uuid.uuid4()
    account_ids_str = [str(a) for a in account_ids]

    await ErasureRepository(session).create_batch(
        request_id, user_id, account_ids_str, ERASURE_SERVICES
    )
    session.add(
        AuditLog(
            actor_identity_id=user_id,
            account_id=None,
            action="account.erasure_requested",
            payload={
                "request_id": str(request_id),
                "user_id": str(user_id) if user_id else None,
                "account_ids": account_ids_str,
                "services": list(ERASURE_SERVICES),
            },
        )
    )
    await session.commit()
    logger.info(
        "Effacement RGPD demandé : request_id=%s user_id=%s comptes=%d",
        request_id,
        user_id,
        len(account_ids_str),
    )
    return request_id


async def process_erasure_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    client: ErasureClient | None = None,
) -> list[str]:
    """Exécute l'effacement pour toutes les cibles non terminées d'une requête.

    Idempotent : ne traite que les cibles ``!= done``. Retourne la liste des
    services encore en échec (à rejouer).
    """
    client = client or ErasureClient()
    repo = ErasureRepository(session)
    targets = await repo.list_unfinished(request_id)

    still_failed: list[str] = []
    for target in targets:
        user_id = str(target.user_id) if target.user_id else None
        try:
            deleted = await client.erase(target.service, target.account_ids, user_id)
            await repo.mark(target, "done", deleted_count=deleted)
            logger.info(
                "Effacement %s ok (request=%s, %s ligne(s))",
                target.service,
                request_id,
                deleted,
            )
        except Exception as exc:  # noqa: BLE001 — on journalise et on rejoue
            await repo.mark(target, "failed", error=str(exc))
            still_failed.append(target.service)
            logger.warning(
                "Effacement %s échoué (request=%s) : %s",
                target.service,
                request_id,
                exc,
            )
    return still_failed


def schedule_erasure(request_id: uuid.UUID) -> None:
    """Programme la tâche Celery d'effacement (import paresseux de Celery).

    Résilient : si le broker est indisponible, on journalise sans faire échouer
    la suppression de compte — les cibles ``pending`` du journal permettent un
    rejeu ultérieur.
    """
    try:
        from app.tasks.erasure import erase_account_data_task

        # retry=False : on ne boucle pas sur la (re)connexion au broker ; en cas
        # d'indisponibilité on tombe dans l'except et le journal prend le relais.
        erase_account_data_task.apply_async((str(request_id),), retry=False)
    except Exception as exc:  # noqa: BLE001 — best-effort, le journal est la source de vérité
        logger.error(
            "Programmation de l'effacement échouée (request=%s) : %s — rejeu possible via le journal",
            request_id,
            exc,
        )
