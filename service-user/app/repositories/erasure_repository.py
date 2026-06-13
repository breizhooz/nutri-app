"""Repository du journal d'effacement RGPD (erasure_targets)."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.erasure import ErasureTarget

logger = logging.getLogger(__name__)


class ErasureRepository:
    """Persistence du journal d'effacement cross-service."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self.session = session

    async def create_batch(
        self,
        request_id: uuid.UUID,
        user_id: uuid.UUID | None,
        account_ids: list[str],
        services: tuple[str, ...],
    ) -> None:
        """Crée une cible ``pending`` par service pour une requête d'effacement."""
        for service in services:
            self.session.add(
                ErasureTarget(
                    request_id=request_id,
                    user_id=user_id,
                    account_ids=account_ids,
                    service=service,
                )
            )
        await self.session.commit()

    async def list_unfinished(self, request_id: uuid.UUID) -> list[ErasureTarget]:
        """Retourne les cibles d'une requête qui ne sont pas encore ``done``."""
        result = await self.session.execute(
            select(ErasureTarget).where(
                ErasureTarget.request_id == request_id,
                ErasureTarget.status != "done",
            )
        )
        return list(result.scalars().all())

    async def mark(
        self,
        target: ErasureTarget,
        status: str,
        *,
        deleted_count: int | None = None,
        error: str | None = None,
    ) -> None:
        """Met à jour le statut d'une cible (incrémente le compteur de tentatives)."""
        target.status = status
        target.attempts += 1
        target.deleted_count = deleted_count
        target.last_error = error
        await self.session.commit()
