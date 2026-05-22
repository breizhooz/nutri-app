"""Routes de suivi corporel : composition et mensurations datées."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, get_locale
from app.db.session import get_session
from app.i18n import t
from app.repositories.profile_repository import ProfileRepository
from app.schemas.tracker import (
    BodyCompositionCreate,
    BodyCompositionResponse,
    BodyMeasurementsCreate,
    BodyMeasurementsResponse,
)
from app.services.tracker_service import TrackerService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_profile_id(
    user_id: uuid.UUID, session: AsyncSession, locale: str
) -> uuid.UUID:
    """Résout le profile_id depuis le user_id. Lève 404 si le profil est absent."""
    profile = await ProfileRepository(session).get_by_user_id(user_id)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale)
        )
    return profile.id


@router.post(
    "/me/composition",
    response_model=BodyCompositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_composition(
    request: Request,
    data: BodyCompositionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> BodyCompositionResponse:
    """Ajoute un snapshot de composition corporelle daté."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    snap = await TrackerService(session).add_composition(profile_id, data)
    return BodyCompositionResponse.model_validate(snap)


@router.get("/me/composition", response_model=list[BodyCompositionResponse])
async def list_composition(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[BodyCompositionResponse]:
    """Retourne l'historique de composition corporelle du plus récent au plus ancien."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    items = await TrackerService(session).list_composition(profile_id)
    return [BodyCompositionResponse.model_validate(s) for s in items]


@router.delete("/me/composition/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_composition(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un snapshot de composition par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await TrackerService(session).delete_composition(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("composition.not_found", locale)
        )


@router.post(
    "/me/measurements",
    response_model=BodyMeasurementsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_measurements(
    request: Request,
    data: BodyMeasurementsCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> BodyMeasurementsResponse:
    """Ajoute un snapshot de mensurations corporelles daté."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    snap = await TrackerService(session).add_measurements(profile_id, data)
    return BodyMeasurementsResponse.model_validate(snap)


@router.get("/me/measurements", response_model=list[BodyMeasurementsResponse])
async def list_measurements(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[BodyMeasurementsResponse]:
    """Retourne l'historique des mensurations du plus récent au plus ancien."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    items = await TrackerService(session).list_measurements(profile_id)
    return [BodyMeasurementsResponse.model_validate(s) for s in items]


@router.delete("/me/measurements/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurements(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un snapshot de mensurations par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await TrackerService(session).delete_measurements(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("measurement.not_found", locale)
        )
