"""Schémas de gestion de la session Instagram (vue admin)."""

from pydantic import BaseModel, Field


class InstagramSessionUpdate(BaseModel):
    """Cookie ``sessionid`` du navigateur fourni par un admin pour ré-authentifier."""

    session_id: str = Field(
        ...,
        min_length=1,
        description="Valeur du cookie 'sessionid' copiée depuis instagram.com.",
    )
    # Optionnel : par défaut le compte configuré (INSTAGRAM_USERNAME) est utilisé.
    username: str | None = None


class InstagramSessionResult(BaseModel):
    """Résultat d'une mise à jour réussie : le compte effectivement authentifié."""

    username: str


class InstagramSessionInfo(BaseModel):
    """État de la session enregistrée (sans jamais exposer le cookie sessionid)."""

    configured: bool
    username: str | None = None
    updated_at: str | None = None  # ISO 8601 — date d'insertion du sessionid
