"""Route interne d'effacement RGPD (art. 17), gardée par token de service."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.repositories import erasure
from app.schemas.internal import ErasureRequest, ErasureResponse

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
