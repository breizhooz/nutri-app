"""Routes de suivi corporel : composition et mensurations datées.

Bornées par le compte actif (multicomptes) via ``read_profile_id`` /
``write_profile_id`` (scope ``profile:read`` / ``profile:write``).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_locale, read_profile_id, write_profile_id
from app.db.session import get_session
from app.i18n import t
from app.schemas.tracker import (
    BodyCompositionCreate,
    BodyCompositionResponse,
    BodyMeasurementsCreate,
    BodyMeasurementsResponse,
)
from app.services.tracker_service import TrackerService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/me/composition",
    response_model=BodyCompositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_composition(
    data: BodyCompositionCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> BodyCompositionResponse:
    """Ajoute un snapshot de composition corporelle daté."""
    snap = await TrackerService(session).add_composition(profile_id, data)
    return BodyCompositionResponse.model_validate(snap)


@router.get("/me/composition", response_model=list[BodyCompositionResponse])
async def list_composition(
    profile_id: uuid.UUID = Depends(read_profile_id),
    session: AsyncSession = Depends(get_session),
) -> list[BodyCompositionResponse]:
    """Retourne l'historique de composition corporelle du plus récent au plus ancien."""
    items = await TrackerService(session).list_composition(profile_id)
    return [BodyCompositionResponse.model_validate(s) for s in items]


@router.delete("/me/composition/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_composition(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un snapshot de composition par son slug."""
    if not await TrackerService(session).delete_composition(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=t.get("composition.not_found", get_locale(request)),
        )


@router.post(
    "/me/measurements",
    response_model=BodyMeasurementsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_measurements(
    data: BodyMeasurementsCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> BodyMeasurementsResponse:
    """Ajoute un snapshot de mensurations corporelles daté."""
    snap = await TrackerService(session).add_measurements(profile_id, data)
    return BodyMeasurementsResponse.model_validate(snap)


@router.get("/me/measurements", response_model=list[BodyMeasurementsResponse])
async def list_measurements(
    profile_id: uuid.UUID = Depends(read_profile_id),
    session: AsyncSession = Depends(get_session),
) -> list[BodyMeasurementsResponse]:
    """Retourne l'historique des mensurations du plus récent au plus ancien."""
    items = await TrackerService(session).list_measurements(profile_id)
    return [BodyMeasurementsResponse.model_validate(s) for s in items]


@router.delete("/me/measurements/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurements(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un snapshot de mensurations par son slug."""
    if not await TrackerService(session).delete_measurements(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=t.get("measurement.not_found", get_locale(request)),
        )
