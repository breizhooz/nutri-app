"""Routes internes (inter-service), réservées aux autres microservices.

Effacement RGPD (art. 17) : purge le dossier profil d'un compte sur demande de
service-user. Gardé par ``verify_service_token``.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.repositories.erasure_repository import ErasureRepository
from app.schemas.internal import ErasureRequest, ErasureResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/erasure", response_model=ErasureResponse)
async def erase_account_data(
    payload: ErasureRequest,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> ErasureResponse:
    """Efface le dossier profil d'un ou plusieurs comptes (idempotent)."""
    deleted = await ErasureRepository(session).erase_by_accounts(
        payload.account_ids, payload.user_id
    )
    return ErasureResponse(deleted=deleted)
