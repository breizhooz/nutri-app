"""Schémas des endpoints internes (inter-service)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ErasureRequest(BaseModel):
    """Demande d'effacement RGPD (art. 17) émise par service-user.

    Porte les deux clés possibles : ``account_ids`` (comptes purgés) et
    ``user_id`` (identité). service-notification purge par ``user_id``.
    """

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ErasureResponse(BaseModel):
    """Compte-rendu d'effacement (idempotent) : nombre de lignes supprimées."""

    model_config = ConfigDict(frozen=True)

    deleted: int
