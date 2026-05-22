"""Service métier pour le profil principal."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import ProfileCreate, ProfileUpdate

logger = logging.getLogger(__name__)


class ProfileService:
    """Logique métier du profil : création, lecture, mise à jour."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le service avec une session — commit appelé ici uniquement."""
        self._session = session
        self._repo = ProfileRepository(session)

    async def create(self, user_id: uuid.UUID, data: ProfileCreate) -> Profile:
        """Crée un profil pour l'utilisateur donné.

        Lève ValueError('already_exists') si un profil existe déjà.
        """
        if await self._repo.get_by_user_id(user_id):
            logger.warning(
                "Tentative de création d'un profil en double pour user_id=%s", user_id
            )
            raise ValueError("already_exists")

        slug = await self._repo.resolve_slug(Profile, f"profile-{str(user_id)[:8]}")
        profile = Profile(
            user_id=user_id,
            slug=slug,
            date_of_birth=data.date_of_birth,
            biological_sex=data.biological_sex,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            target_weight_kg=data.target_weight_kg,
        )
        self._repo.add(profile)
        await self._session.commit()
        await self._session.refresh(profile)
        logger.info("Profil créé : slug=%s user_id=%s", profile.slug, user_id)
        return profile

    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        """Retourne le profil d'un utilisateur, ou None."""
        return await self._repo.get_by_user_id(user_id)

    async def update(self, user_id: uuid.UUID, data: ProfileUpdate) -> Profile | None:
        """Met à jour les champs fournis du profil. Retourne None si le profil est introuvable."""
        profile = await self._repo.get_by_user_id(user_id)
        if not profile:
            logger.warning("Profil introuvable pour mise à jour user_id=%s", user_id)
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)

        await self._session.commit()
        await self._session.refresh(profile)
        logger.info("Profil mis à jour : user_id=%s", user_id)
        return profile
