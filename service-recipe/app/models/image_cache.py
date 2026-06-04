from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.abstract_model import AbstractModel


class ImageSearchCache(AbstractModel):
    """Cache persistant des résultats de recherche d'images Unsplash.

    Indexé par mot-clé normalisé (cf. ``normalize_keyword``) : plusieurs recettes
    qui partagent un même titre réutilisent les propositions CDN déjà récupérées,
    ce qui évite de retaper l'API Unsplash (quota limité) et permet d'en demander
    davantage par requête puisque le coût est mutualisé.
    """

    __tablename__ = "image_search_cache"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Mot-clé normalisé (minuscule, espaces compactés) servant de clé de cache.
    keyword: Mapped[str] = mapped_column(String(300), unique=True, index=True)

    # Liste de propositions (dicts ImageSuggestion : urls CDN + métadonnées).
    suggestions: Mapped[list[Any]] = mapped_column(
        JSON, default=list, server_default="[]"
    )

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )
