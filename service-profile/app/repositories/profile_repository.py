"""Repository Profile — accès aux données du profil principal."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ProfileRepository(BaseRepository):
    """Opérations de persistence pour le modèle Profile."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository Profile."""
        super().__init__(session)

    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        """Retourne le profil associé à un user_id, ou None s'il n'existe pas."""
        logger.debug("Recherche profile pour user_id=%s", user_id)
        result = await self._session.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def add(self, profile: Profile) -> None:
        """Enregistre un nouveau Profile dans la session (sans commit)."""
        self._session.add(profile)