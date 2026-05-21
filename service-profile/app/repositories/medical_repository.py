"""Repository Medical — blessures, pathologies, allergies, médicaments."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_allergy import FoodAllergy
from app.models.injury import Injury
from app.models.medical_condition import MedicalCondition
from app.models.medication import Medication
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

_MedicalModel = Injury | MedicalCondition | FoodAllergy | Medication


class MedicalRepository(BaseRepository):
    """Opérations de persistence pour les données médicales et de sécurité."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository Medical."""
        super().__init__(session)

    def add(self, obj: _MedicalModel) -> None:
        """Ajoute un objet médical à la session (sans commit)."""
        self._session.add(obj)

    async def delete(self, obj: _MedicalModel) -> None:
        """Supprime un objet médical de la session."""
        await self._session.delete(obj)

    async def list_injuries(self, profile_id: uuid.UUID) -> list[Injury]:
        """Retourne toutes les blessures d'un profil."""
        result = await self._session.execute(
            select(Injury).where(Injury.profile_id == profile_id).order_by(Injury.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_injury(self, slug: str, profile_id: uuid.UUID) -> Injury | None:
        """Retourne une blessure par slug et profile_id, ou None."""
        result = await self._session.execute(
            select(Injury).where(Injury.slug == slug, Injury.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_conditions(self, profile_id: uuid.UUID) -> list[MedicalCondition]:
        """Retourne toutes les pathologies d'un profil."""
        result = await self._session.execute(
            select(MedicalCondition)
            .where(MedicalCondition.profile_id == profile_id)
            .order_by(MedicalCondition.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_condition(self, slug: str, profile_id: uuid.UUID) -> MedicalCondition | None:
        """Retourne une pathologie par slug et profile_id, ou None."""
        result = await self._session.execute(
            select(MedicalCondition).where(
                MedicalCondition.slug == slug, MedicalCondition.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def list_allergies(self, profile_id: uuid.UUID) -> list[FoodAllergy]:
        """Retourne toutes les allergies d'un profil."""
        result = await self._session.execute(
            select(FoodAllergy)
            .where(FoodAllergy.profile_id == profile_id)
            .order_by(FoodAllergy.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_allergy(self, slug: str, profile_id: uuid.UUID) -> FoodAllergy | None:
        """Retourne une allergie par slug et profile_id, ou None."""
        result = await self._session.execute(
            select(FoodAllergy).where(
                FoodAllergy.slug == slug, FoodAllergy.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def list_medications(self, profile_id: uuid.UUID) -> list[Medication]:
        """Retourne tous les traitements d'un profil."""
        result = await self._session.execute(
            select(Medication)
            .where(Medication.profile_id == profile_id)
            .order_by(Medication.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_medication(self, slug: str, profile_id: uuid.UUID) -> Medication | None:
        """Retourne un traitement par slug et profile_id, ou None."""
        result = await self._session.execute(
            select(Medication).where(
                Medication.slug == slug, Medication.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()