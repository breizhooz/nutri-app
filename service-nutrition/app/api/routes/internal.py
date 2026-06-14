"""Routes internes (inter-service), gardées par token de service.

Effacement RGPD (art. 17) et portabilité (art. 20) des données nutrition.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.repositories.erasure_repository import ErasureRepository
from app.repositories.export_repository import ExportRepository
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
    """Efface les macro_errors d'un ou plusieurs comptes (idempotent)."""
    deleted = await ErasureRepository(session).erase_by_accounts(
        payload.account_ids, payload.user_id
    )
    return ErasureResponse(deleted=deleted)


@router.post("/export", response_model=ExportResponse)
async def export_account_data(
    payload: ExportRequest,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> ExportResponse:
    """Exporte les macro_errors d'un ou plusieurs comptes (RGPD art. 20)."""
    data = await ExportRepository(session).export_by_accounts(
        payload.account_ids, payload.user_id
    )
    return ExportResponse(data=data)
