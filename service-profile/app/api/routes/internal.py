"""Routes internes (inter-service), réservées aux autres microservices.

Résumé nutritionnel d'un compte (service-menu, service-recipe). Effacement RGPD
(art. 17) : purge le profil d'un compte sur demande de service-user. Portabilité
(art. 20) : export du profil. Tous gardés par ``verify_service_token``.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_locale, verify_service_token
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.erasure_repository import ErasureRepository
from app.repositories.export_repository import ExportRepository
from app.schemas.internal import (
    ErasureRequest,
    ErasureResponse,
    ExportRequest,
    ExportResponse,
)
from app.schemas.profile import NutritionSummary
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/accounts/{account_id}/nutrition-summary", response_model=NutritionSummary)
async def nutrition_summary(
    account_id: uuid.UUID,
    request: Request,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> NutritionSummary:
    """Objectif, régime, exclusions et cibles du compte (404 sans profil)."""
    summary = await ProfileService(session).summary(account_id)
    if summary is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=t.get("profile.not_found", get_locale(request)),
        )
    return summary


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


@router.post("/export", response_model=ExportResponse)
async def export_account_data(
    payload: ExportRequest,
    _: None = Depends(verify_service_token),
    session: AsyncSession = Depends(get_session),
) -> ExportResponse:
    """Exporte le dossier profil d'un ou plusieurs comptes (RGPD art. 20)."""
    data = await ExportRepository(session).export_by_accounts(
        payload.account_ids, payload.user_id
    )
    return ExportResponse(data=data)
