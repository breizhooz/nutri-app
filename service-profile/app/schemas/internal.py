"""Schémas des endpoints internes (inter-service)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ErasureRequest(BaseModel):
    """Demande d'effacement RGPD (art. 17) émise par service-user.

    Porte les deux clés possibles : ``account_ids`` (comptes personnels purgés)
    et ``user_id`` (identité, legacy). Chaque service purge selon la clé qu'il
    possède — ici le profil est résolu par l'une ou l'autre.
    """

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ErasureResponse(BaseModel):
    """Compte-rendu d'effacement (idempotent) : nombre de profils supprimés."""

    model_config = ConfigDict(frozen=True)

    deleted: int
