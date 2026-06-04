from typing import Any

from pydantic import BaseModel


class SpoonacularShakeResponse(BaseModel):
    """Recette tirée du cache Spoonacular pour le widget « Shake ta recette ».

    ``description`` est le résumé court (HTML nettoyé, tronqué) ; ``payload`` porte
    la recette Spoonacular complète, consommée par la modal du front.
    """

    spoonacular_id: int
    title: str
    description: str
    image_url: str | None = None
    source_url: str | None = None
    payload: dict[str, Any]
