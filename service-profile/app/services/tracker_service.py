"""Service métier pour le suivi corporel (composition et mensurations)."""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_composition_snapshot import BodyCompositionSnapshot
from app.models.body_measurements_snapshot import BodyMeasurementsSnapshot
from app.repositories.tracker_repository import TrackerRepository
from app.schemas.tracker import BodyCompositionCreate, BodyMeasurementsCreate

logger = logging.getLogger(__name__)


class TrackerService:
    """Logique métier du suivi corporel : snapshots composition et mensurations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le service avec une session — commit appelé ici uniquement."""
        self._session = session
        self._repo = TrackerRepository(session)

    async def add_composition(
        self, profile_id: uuid.UUID, data: BodyCompositionCreate
    ) -> BodyCompositionSnapshot:
        """Ajoute un snapshot de composition corporelle."""
        slug = await self._repo.resolve_slug(
            BodyCompositionSnapshot, f"compo-{str(profile_id)[:8]}-{data.measured_at}"
        )
        snap = BodyCompositionSnapshot(
            profile_id=profile_id, slug=slug,
            measured_at=data.measured_at,
            body_fat_percentage=data.body_fat_percentage,
            lean_mass_kg=data.lean_mass_kg,
            bone_mass_kg=data.bone_mass_kg,
            water_percentage=data.water_percentage,
        )
        self._repo.add_composition(snap)
        await self._session.commit()
        await self._session.refresh(snap)
        logger.info("Snapshot composition ajouté : profile_id=%s date=%s", profile_id, data.measured_at)
        return snap

    async def list_composition(self, profile_id: uuid.UUID) -> list[BodyCompositionSnapshot]:
        """Retourne l'historique de composition corporelle."""
        return await self._repo.list_composition(profile_id)

    async def delete_composition(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime un snapshot de composition. Retourne False si introuvable."""
        snap = await self._repo.get_composition_by_slug(slug, profile_id)
        if not snap:
            logger.warning("Snapshot composition introuvable : slug=%s", slug)
            return False
        await self._repo.delete_composition(snap)
        await self._session.commit()
        return True

    async def add_measurements(
        self, profile_id: uuid.UUID, data: BodyMeasurementsCreate
    ) -> BodyMeasurementsSnapshot:
        """Ajoute un snapshot de mensurations corporelles."""
        slug = await self._repo.resolve_slug(
            BodyMeasurementsSnapshot, f"mensuration-{str(profile_id)[:8]}-{data.measured_at}"
        )
        snap = BodyMeasurementsSnapshot(
            profile_id=profile_id, slug=slug,
            measured_at=data.measured_at,
            waist_cm=data.waist_cm, hips_cm=data.hips_cm,
            chest_cm=data.chest_cm, shoulders_cm=data.shoulders_cm,
            left_arm_cm=data.left_arm_cm, right_arm_cm=data.right_arm_cm,
            left_thigh_cm=data.left_thigh_cm, right_thigh_cm=data.right_thigh_cm,
        )
        self._repo.add_measurements(snap)
        await self._session.commit()
        await self._session.refresh(snap)
        logger.info("Snapshot mensurations ajouté : profile_id=%s date=%s", profile_id, data.measured_at)
        return snap

    async def list_measurements(self, profile_id: uuid.UUID) -> list[BodyMeasurementsSnapshot]:
        """Retourne l'historique des mensurations."""
        return await self._repo.list_measurements(profile_id)

    async def delete_measurements(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime un snapshot de mensurations. Retourne False si introuvable."""
        snap = await self._repo.get_measurements_by_slug(slug, profile_id)
        if not snap:
            return False
        await self._repo.delete_measurements(snap)
        await self._session.commit()
        return True