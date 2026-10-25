"""Logique du profil nutritionnel : mise à jour partielle et résumé inter-service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_profile import NutritionProfile
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import (
    NutritionSummary,
    ProfileUpdate,
    RulesSummary,
    TargetsSummary,
)


class ProfileService:
    """Profil d'un compte : lecture, upsert partiel, résumé pour menus/recherche."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = ProfileRepository(session)

    async def get(self, account_id: uuid.UUID) -> NutritionProfile | None:
        return await self._repository.get_by_account(account_id)

    async def upsert(
        self, account_id: uuid.UUID, data: ProfileUpdate
    ) -> NutritionProfile:
        """Crée le profil au premier enregistrement ; sinon ne modifie que les
        champs envoyés."""
        profile = await self._repository.get_by_account(account_id)
        if profile is None:
            profile = NutritionProfile(account_id=account_id, excluded_foods=[])
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)
        return await self._repository.save(profile)

    async def summary(self, account_id: uuid.UUID) -> NutritionSummary | None:
        profile = await self._repository.get_by_account(account_id)
        if profile is None:
            return None
        targets = None
        if profile.target_calories_kcal is not None:
            targets = TargetsSummary(
                calories=profile.target_calories_kcal,
                proteines=profile.target_proteins_g,
                glucides=profile.target_carbs_g,
                lipides=profile.target_fats_g,
            )
        return NutritionSummary(
            account_id=profile.account_id,
            main_goal=profile.main_goal.value,
            diet_type=profile.diet_type.value,
            excluded_foods=list(profile.excluded_foods or []),
            targets=targets,
            rules=RulesSummary(
                enabled=profile.nutrition_rules_enabled,
                variety_pct=profile.rules_variety_pct,
                override_calories=profile.rules_override_calories,
                override_proteines=profile.rules_override_proteines,
            ),
        )
