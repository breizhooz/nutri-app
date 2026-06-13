"""Schémas des endpoints internes (inter-service)."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErasureRequest(BaseModel):
    """Demande d'effacement RGPD (art. 17) émise par service-user.

    Porte les deux clés possibles : ``account_ids`` (comptes personnels purgés)
    et ``user_id`` (identité). service-menu purge par ``account_id``.
    """

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ErasureResponse(BaseModel):
    """Compte-rendu d'effacement (idempotent) : nombre de menus supprimés."""

    model_config = ConfigDict(frozen=True)

    deleted: int


class ExportRequest(BaseModel):
    """Demande d'export RGPD (art. 20). service-menu exporte par ``account_id``."""

    model_config = ConfigDict(frozen=True)

    account_ids: list[uuid.UUID] = Field(default_factory=list)
    user_id: uuid.UUID | None = None


class ExportResponse(BaseModel):
    """Données exportées (structure libre, JSON-sérialisable)."""

    data: dict[str, Any] = Field(default_factory=dict)
