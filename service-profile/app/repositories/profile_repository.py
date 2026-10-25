"""Repository du profil nutritionnel (un par compte)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_profile import NutritionProfile


class ProfileRepository:
    """Accès aux profils nutritionnels, bornés par ``account_id``."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session fournie."""
        self._session = session

    async def get_by_account(self, account_id: uuid.UUID) -> NutritionProfile | None:
        result = await self._session.execute(
            select(NutritionProfile).where(NutritionProfile.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def save(self, profile: NutritionProfile) -> NutritionProfile:
        self._session.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        return profile
