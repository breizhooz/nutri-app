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

    async def get_by_account_id(self, account_id: uuid.UUID) -> Profile | None:
        """Retourne le profil du compte (clé de partition multicomptes), ou None.

        Résolution de dossier des routes ``/me*`` : le JWT de contexte porte
        ``act_account`` et le dossier est borné par ce compte.
        """
        logger.debug("Recherche profile pour account_id=%s", account_id)
        result = await self._session.execute(
            select(Profile).where(Profile.account_id == account_id)
        )
        return result.scalar_one_or_none()

    def add(self, profile: Profile) -> None:
        """Enregistre un nouveau Profile dans la session (sans commit)."""
        self._session.add(profile)
