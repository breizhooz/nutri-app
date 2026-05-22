"""Repository Tracker — snapshots de composition et de mensurations."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_composition_snapshot import BodyCompositionSnapshot
from app.models.body_measurements_snapshot import BodyMeasurementsSnapshot
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TrackerRepository(BaseRepository):
    """Opérations de persistence pour les snapshots corporels."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository Tracker."""
        super().__init__(session)

    def add_composition(self, snap: BodyCompositionSnapshot) -> None:
        """Ajoute un snapshot de composition à la session."""
        self._session.add(snap)

    async def list_composition(
        self, profile_id: uuid.UUID
    ) -> list[BodyCompositionSnapshot]:
        """Retourne tous les snapshots de composition, du plus récent au plus ancien."""
        result = await self._session.execute(
            select(BodyCompositionSnapshot)
            .where(BodyCompositionSnapshot.profile_id == profile_id)
            .order_by(BodyCompositionSnapshot.measured_at.desc())
        )
        return list(result.scalars().all())

    async def get_composition_by_slug(
        self, slug: str, profile_id: uuid.UUID
    ) -> BodyCompositionSnapshot | None:
        """Retourne un snapshot de composition par slug, ou None."""
        result = await self._session.execute(
            select(BodyCompositionSnapshot).where(
                BodyCompositionSnapshot.slug == slug,
                BodyCompositionSnapshot.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_composition(self, snap: BodyCompositionSnapshot) -> None:
        """Supprime un snapshot de composition de la session."""
        await self._session.delete(snap)

    def add_measurements(self, snap: BodyMeasurementsSnapshot) -> None:
        """Ajoute un snapshot de mensurations à la session."""
        self._session.add(snap)

    async def list_measurements(
        self, profile_id: uuid.UUID
    ) -> list[BodyMeasurementsSnapshot]:
        """Retourne toutes les mensurations, du plus récent au plus ancien."""
        result = await self._session.execute(
            select(BodyMeasurementsSnapshot)
            .where(BodyMeasurementsSnapshot.profile_id == profile_id)
            .order_by(BodyMeasurementsSnapshot.measured_at.desc())
        )
        return list(result.scalars().all())

    async def get_measurements_by_slug(
        self, slug: str, profile_id: uuid.UUID
    ) -> BodyMeasurementsSnapshot | None:
        """Retourne un snapshot de mensurations par slug, ou None."""
        result = await self._session.execute(
            select(BodyMeasurementsSnapshot).where(
                BodyMeasurementsSnapshot.slug == slug,
                BodyMeasurementsSnapshot.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_measurements(self, snap: BodyMeasurementsSnapshot) -> None:
        """Supprime un snapshot de mensurations de la session."""
        await self._session.delete(snap)
