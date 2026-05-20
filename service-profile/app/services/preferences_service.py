"""Service métier pour les préférences et personnalisation."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.excluded_food import ExcludedFood
from app.models.lifestyle_profile import LifestyleProfile
from app.models.nutrition_preferences import NutritionPreferences
from app.models.performance_metric import PerformanceMetric
from app.models.sports_profile import SportsProfile
from app.repositories.preferences_repository import PreferencesRepository
from app.schemas.preferences import (
    ExcludedFoodCreate, LifestyleProfileCreate,
    NutritionPreferencesCreate, PerformanceMetricCreate, SportsProfileCreate,
)

logger = logging.getLogger(__name__)


class PreferencesService:
    """Logique métier des préférences : sports, lifestyle, nutrition, performances, exclusions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le service avec une session — commit appelé ici uniquement."""
        self._session = session
        self._repo = PreferencesRepository(session)

    async def upsert_sports(self, profile_id: uuid.UUID, data: SportsProfileCreate) -> SportsProfile:
        """Crée ou met à jour le profil sportif (upsert)."""
        existing = await self._repo.get_sports(profile_id)
        if existing:
            for field, value in data.model_dump().items():
                setattr(existing, field, value)
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.commit()
            await self._session.refresh(existing)
            logger.info("Profil sportif mis à jour : profile_id=%s", profile_id)
            return existing

        slug = await self._repo.resolve_slug(SportsProfile, f"sports-{str(profile_id)[:8]}")
        obj = SportsProfile(profile_id=profile_id, slug=slug, **data.model_dump())
        self._repo.add_sports(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        logger.info("Profil sportif créé : profile_id=%s", profile_id)
        return obj

    async def get_sports(self, profile_id: uuid.UUID) -> SportsProfile | None:
        """Retourne le profil sportif ou None."""
        return await self._repo.get_sports(profile_id)

    async def upsert_lifestyle(self, profile_id: uuid.UUID, data: LifestyleProfileCreate) -> LifestyleProfile:
        """Crée ou met à jour le profil de mode de vie (upsert)."""
        existing = await self._repo.get_lifestyle(profile_id)
        if existing:
            for field, value in data.model_dump(exclude_none=True).items():
                setattr(existing, field, value)
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.commit()
            await self._session.refresh(existing)
            return existing

        slug = await self._repo.resolve_slug(LifestyleProfile, f"lifestyle-{str(profile_id)[:8]}")
        obj = LifestyleProfile(profile_id=profile_id, slug=slug, **data.model_dump())
        self._repo.add_lifestyle(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def get_lifestyle(self, profile_id: uuid.UUID) -> LifestyleProfile | None:
        """Retourne le lifestyle ou None."""
        return await self._repo.get_lifestyle(profile_id)

    async def upsert_nutrition(self, profile_id: uuid.UUID, data: NutritionPreferencesCreate) -> NutritionPreferences:
        """Crée ou met à jour les préférences nutritionnelles (upsert)."""
        existing = await self._repo.get_nutrition(profile_id)
        if existing:
            for field, value in data.model_dump(exclude_none=True).items():
                setattr(existing, field, value)
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.commit()
            await self._session.refresh(existing)
            return existing

        slug = await self._repo.resolve_slug(NutritionPreferences, f"nutrition-{str(profile_id)[:8]}")
        obj = NutritionPreferences(profile_id=profile_id, slug=slug, **data.model_dump())
        self._repo.add_nutrition(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def get_nutrition(self, profile_id: uuid.UUID) -> NutritionPreferences | None:
        """Retourne les préférences nutritionnelles ou None."""
        return await self._repo.get_nutrition(profile_id)

    async def add_performance(self, profile_id: uuid.UUID, data: PerformanceMetricCreate) -> PerformanceMetric:
        """Ajoute une métrique de performance datée."""
        slug = await self._repo.resolve_slug(
            PerformanceMetric, f"perf-{str(profile_id)[:8]}-{data.measured_at}"
        )
        obj = PerformanceMetric(profile_id=profile_id, slug=slug, **data.model_dump())
        self._repo.add_performance(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        logger.info("Métrique perf ajoutée : profile_id=%s date=%s", profile_id, data.measured_at)
        return obj

    async def list_performance(self, profile_id: uuid.UUID) -> list[PerformanceMetric]:
        """Retourne l'historique des métriques de performance."""
        return await self._repo.list_performance(profile_id)

    async def delete_performance(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Supprime une métrique de performance. Retourne False si introuvable."""
        obj = await self._repo.get_performance_by_slug(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete_performance(obj)
        await self._session.commit()
        return True

    async def add_excluded_food(self, profile_id: uuid.UUID, data: ExcludedFoodCreate) -> ExcludedFood:
        """Ajoute un aliment à la liste d'exclusion."""
        slug = await self._repo.resolve_slug(ExcludedFood, data.food_name)
        obj = ExcludedFood(profile_id=profile_id, slug=slug, **data.model_dump())
        self._repo.add_excluded_food(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def list_excluded_foods(self, profile_id: uuid.UUID) -> list[ExcludedFood]:
        """Retourne tous les aliments exclus du profil."""
        return await self._repo.list_excluded_foods(profile_id)

    async def delete_excluded_food(self, slug: str, profile_id: uuid.UUID) -> bool:
        """Retire un aliment de la liste d'exclusion. Retourne False si introuvable."""
        obj = await self._repo.get_excluded_food_by_slug(slug, profile_id)
        if not obj:
            return False
        await self._repo.delete_excluded_food(obj)
        await self._session.commit()
        return True