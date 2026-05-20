"""Repository Preferences — sports, performances, lifestyle, nutrition, aliments exclus."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.excluded_food import ExcludedFood
from app.models.lifestyle_profile import LifestyleProfile
from app.models.nutrition_preferences import NutritionPreferences
from app.models.performance_metric import PerformanceMetric
from app.models.sports_profile import SportsProfile
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PreferencesRepository(BaseRepository):
    """Opérations de persistence pour les préférences et personnalisation."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository Preferences."""
        super().__init__(session)

    async def get_sports(self, profile_id: uuid.UUID) -> SportsProfile | None:
        """Retourne le profil sportif d'un profil, ou None."""
        result = await self._session.execute(
            select(SportsProfile).where(SportsProfile.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    def add_sports(self, obj: SportsProfile) -> None:
        """Ajoute ou met à jour le profil sportif dans la session."""
        self._session.add(obj)

    async def get_lifestyle(self, profile_id: uuid.UUID) -> LifestyleProfile | None:
        """Retourne le profil de mode de vie d'un profil, ou None."""
        result = await self._session.execute(
            select(LifestyleProfile).where(LifestyleProfile.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    def add_lifestyle(self, obj: LifestyleProfile) -> None:
        """Ajoute ou met à jour le lifestyle dans la session."""
        self._session.add(obj)

    async def get_nutrition(self, profile_id: uuid.UUID) -> NutritionPreferences | None:
        """Retourne les préférences nutritionnelles d'un profil, ou None."""
        result = await self._session.execute(
            select(NutritionPreferences).where(NutritionPreferences.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    def add_nutrition(self, obj: NutritionPreferences) -> None:
        """Ajoute ou met à jour les préférences nutritionnelles dans la session."""
        self._session.add(obj)

    def add_performance(self, obj: PerformanceMetric) -> None:
        """Ajoute une métrique de performance dans la session."""
        self._session.add(obj)

    async def list_performance(self, profile_id: uuid.UUID) -> list[PerformanceMetric]:
        """Retourne toutes les métriques de performance, du plus récent au plus ancien."""
        result = await self._session.execute(
            select(PerformanceMetric)
            .where(PerformanceMetric.profile_id == profile_id)
            .order_by(PerformanceMetric.measured_at.desc())
        )
        return list(result.scalars().all())

    async def get_performance_by_slug(
        self, slug: str, profile_id: uuid.UUID
    ) -> PerformanceMetric | None:
        """Retourne une métrique de performance par slug, ou None."""
        result = await self._session.execute(
            select(PerformanceMetric).where(
                PerformanceMetric.slug == slug,
                PerformanceMetric.profile_id == profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_performance(self, obj: PerformanceMetric) -> None:
        """Supprime une métrique de performance de la session."""
        await self._session.delete(obj)

    async def list_excluded_foods(self, profile_id: uuid.UUID) -> list[ExcludedFood]:
        """Retourne tous les aliments exclus d'un profil."""
        result = await self._session.execute(
            select(ExcludedFood)
            .where(ExcludedFood.profile_id == profile_id)
            .order_by(ExcludedFood.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_excluded_food_by_slug(
        self, slug: str, profile_id: uuid.UUID
    ) -> ExcludedFood | None:
        """Retourne un aliment exclu par slug, ou None."""
        result = await self._session.execute(
            select(ExcludedFood).where(
                ExcludedFood.slug == slug, ExcludedFood.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()

    def add_excluded_food(self, obj: ExcludedFood) -> None:
        """Ajoute un aliment exclu dans la session."""
        self._session.add(obj)

    async def delete_excluded_food(self, obj: ExcludedFood) -> None:
        """Supprime un aliment exclu de la session."""
        await self._session.delete(obj)