"""Schémas des endpoints internes (inter-service)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ErasureRequest(BaseModel):
    """Demande d'effacement RGPD (art. 17) émise par service-user.

    Porte les deux clés possibles : ``account_ids`` (comptes purgés) et
    ``user_id`` (identité). service-nutrition purge les ``macro_errors`` par
    l'une ou l'autre (account_id est nullable pour l'existant non rétro-rempli).
    """

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ErasureResponse(BaseModel):
    """Compte-rendu d'effacement (idempotent) : nombre de lignes supprimées."""

    model_config = ConfigDict(frozen=True)

    deleted: int
