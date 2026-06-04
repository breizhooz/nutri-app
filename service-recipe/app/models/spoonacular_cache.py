from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.abstract_model import AbstractModel


class SpoonacularRecipeCache(AbstractModel):
    """Cache des recettes récupérées quotidiennement depuis l'API Spoonacular.

    Une ligne par recette Spoonacular (clé naturelle = ``spoonacular_id``). Le
    payload brut de l'API est conservé tel quel (colonne ``payload``) pour ne rien
    perdre ; quelques champs sont dénormalisés (titre, image, source) afin de lister
    le cache sans désérialiser le JSON. L'upsert par ``spoonacular_id`` garantit
    qu'une même recette tirée plusieurs jours de suite n'est pas dupliquée.
    """

    __tablename__ = "spoonacular_recipe_cache"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identifiant Spoonacular = clé de cache (1 ligne par recette).
    spoonacular_id: Mapped[int] = mapped_column(unique=True, index=True)

    title: Mapped[str] = mapped_column(String(500), default="")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Payload brut renvoyé par l'API Spoonacular (recette complète).
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )
