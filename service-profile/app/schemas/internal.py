"""Schémas des endpoints internes (inter-service)."""

import uuid
from typing import Any

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


class ExportRequest(BaseModel):
    """Demande d'export RGPD (art. 20, portabilité) émise par service-user.

    Mêmes clés que l'effacement : le service rassemble les données du ou des
    comptes (``account_ids``) ou de l'identité (``user_id``).
    """

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ExportResponse(BaseModel):
    """Données exportées d'un service (structure libre, JSON-sérialisable)."""

    data: dict[str, Any] = Field(default_factory=dict)
