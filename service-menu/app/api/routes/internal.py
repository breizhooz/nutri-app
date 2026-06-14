"""Routes internes (inter-service), gardées par token de service.

Effacement RGPD (art. 17) et portabilité (art. 20) des menus d'un compte.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.repositories import erasure, export
from app.schemas.internal import (
    ErasureRequest,
    ErasureResponse,
    ExportRequest,
    ExportResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/erasure", response_model=ErasureResponse)
async def erase_account_data(
    payload: ErasureRequest,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> ErasureResponse:
    """Efface les menus d'un ou plusieurs comptes (idempotent)."""
    deleted = await erasure.erase_by_accounts(
        session, [str(a) for a in payload.account_ids]
    )
    return ErasureResponse(deleted=deleted)


@router.post("/export", response_model=ExportResponse)
async def export_account_data(
    payload: ExportRequest,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> ExportResponse:
    """Exporte les menus d'un ou plusieurs comptes (RGPD art. 20)."""
    data = await export.export_by_accounts(
        session, [str(a) for a in payload.account_ids]
    )
    return ExportResponse(data=data)
