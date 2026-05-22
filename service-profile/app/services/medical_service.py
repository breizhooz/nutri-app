"""Service métier pour les données médicales et de sécurité."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.food_allergy import FoodAllergy
from app.models.injury import Injury
from app.models.medical_condition import MedicalCondition
from app.models.medication import Medication
from app.repositories.medical_repository import MedicalRepository
from app.schemas.medical import (
    FoodAllergyCreate,
    InjuryCreate,
    MedicalConditionCreate,
    MedicationCreate,
)

logger = logging.getLogger(__name__)


class MedicalService:
    """Logique métier des données médicales : blessures, pathologies, allergies, médicaments."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le service avec une session — commit appelé ici uniquement."""
        self._session = session
        self._repo = MedicalRepository(session)

    async def add_injury(self, profile_id: uuid.UUID, data: InjuryCreate) -> Injury:
        """Ajoute une blessure au profil."""
        slug = await self._repo.resolve_slug(
            Injury, f"{data.injury_type}-{data.body_part}"
        )
        obj = Injury(
            profile_id=profile_id,
            slug=slug,
            body_part=data.body_part,
            injury_type=data.injury_type,
            is_current=data.is_current,
            is_chronic=data.is_chronic,
            diagnosed_at=data.diagnosed_at,
            notes=data.notes,
        )
        self._repo.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        logger.info("Blessure ajoutée : profile_id=%s slug=%s", profile_id, obj.slug)
        return obj

    async def list_injuries(self, profile_id: uuid.UUID) -> list[Injury]:
        """Retourne toutes les blessures d'un profil."""
        return await self._repo.list_injuries(profile_id)

    async def delete_injury(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime une blessure. Retourne False si introuvable."""
        obj = await self._repo.get_injury(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete(obj)
        await self._session.commit()
        logger.info("Blessure supprimée : slug=%s", slug)
        return True

    async def add_condition(
        self, profile_id: uuid.UUID, data: MedicalConditionCreate
    ) -> MedicalCondition:
        """Ajoute une pathologie au profil."""
        slug = await self._repo.resolve_slug(MedicalCondition, data.condition_name)
        obj = MedicalCondition(
            profile_id=profile_id,
            slug=slug,
            category=data.category,
            condition_name=data.condition_name,
            is_current=data.is_current,
            notes=data.notes,
        )
        self._repo.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def list_conditions(self, profile_id: uuid.UUID) -> list[MedicalCondition]:
        """Retourne toutes les pathologies d'un profil."""
        return await self._repo.list_conditions(profile_id)

    async def delete_condition(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime une pathologie. Retourne False si introuvable."""
        obj = await self._repo.get_condition(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete(obj)
        await self._session.commit()
        return True

    async def add_allergy(
        self, profile_id: uuid.UUID, data: FoodAllergyCreate
    ) -> FoodAllergy:
        """Ajoute une allergie ou intolérance au profil."""
        slug = await self._repo.resolve_slug(FoodAllergy, data.allergen)
        obj = FoodAllergy(
            profile_id=profile_id,
            slug=slug,
            allergen=data.allergen,
            severity=data.severity,
            notes=data.notes,
        )
        self._repo.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def list_allergies(self, profile_id: uuid.UUID) -> list[FoodAllergy]:
        """Retourne toutes les allergies d'un profil."""
        return await self._repo.list_allergies(profile_id)

    async def delete_allergy(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime une allergie. Retourne False si introuvable."""
        obj = await self._repo.get_allergy(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete(obj)
        await self._session.commit()
        return True

    async def add_medication(
        self, profile_id: uuid.UUID, data: MedicationCreate
    ) -> Medication:
        """Ajoute un traitement médicamenteux au profil."""
        slug = await self._repo.resolve_slug(Medication, data.medication_name)
        obj = Medication(
            profile_id=profile_id,
            slug=slug,
            medication_name=data.medication_name,
            impacts_metabolism=data.impacts_metabolism,
            notes=data.notes,
        )
        self._repo.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def list_medications(self, profile_id: uuid.UUID) -> list[Medication]:
        """Retourne tous les traitements d'un profil."""
        return await self._repo.list_medications(profile_id)

    async def delete_medication(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime un traitement. Retourne False si introuvable."""
        obj = await self._repo.get_medication(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete(obj)
        await self._session.commit()
        return True
