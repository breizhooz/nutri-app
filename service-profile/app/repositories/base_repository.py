"""Repository de base — résolution de slug unique partagée."""
import logging

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BaseRepository:
    """Classe de base pour tous les repositories du service-profile.

    Fournit la résolution de slug unique avec suffixe numérique automatique.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise le repository avec la session SQLAlchemy fournie."""
        self._session = session

    async def resolve_slug(self, model_class: type, base: str) -> str:
        """Génère un slug unique basé sur base, suffixe numérique si collision.

        Exemple : "tendinite-rotulienne" → "tendinite-rotulienne-2" si déjà pris.
        """
        candidate = slugify(base)
        counter = 2
        while True:
            result = await self._session.execute(
                select(model_class.id).where(model_class.slug == candidate)  # type: ignore[attr-defined]
            )
            if result.scalar_one_or_none() is None:
                logger.debug("Slug résolu : '%s'", candidate)
                return candidate
            candidate = f"{slugify(base)}-{counter}"
            counter += 1