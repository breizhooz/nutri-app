"""Routes du profil principal : CRUD + calcul métabolique + endpoint inter-service."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, get_locale, verify_service_token
from app.db.session import get_session
from app.i18n import t
from app.repositories.preferences_repository import PreferencesRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.calculations import CalculationResponse
from app.schemas.profile import ProfileCreate, ProfileResponse, ProfileUpdate
from app.services.calculation_service import CalculationService
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    request: Request,
    data: ProfileCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Crée le profil de l'utilisateur authentifié. HTTP 409 si déjà existant."""
    locale = get_locale(request)
    try:
        profile = await ProfileService(session).create(user_id, data)
    except ValueError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=t.get("profile.already_exists", locale)
        )
    return ProfileResponse.model_validate(profile)


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Retourne le profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile = await ProfileService(session).get_by_user_id(user_id)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale)
        )
    return ProfileResponse.model_validate(profile)


@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    request: Request,
    data: ProfileUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Met à jour les champs fournis du profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile = await ProfileService(session).update(user_id, data)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale)
        )
    return ProfileResponse.model_validate(profile)


@router.get("/me/calculate", response_model=CalculationResponse)
async def calculate_my_profile(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CalculationResponse:
    """Calcule IMC, MB, TDEE, poids idéal et macros pour le profil authentifié."""
    locale = get_locale(request)
    profile_repo = ProfileRepository(session)
    pref_repo = PreferencesRepository(session)

    profile = await profile_repo.get_by_user_id(user_id)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale)
        )

    lifestyle = await pref_repo.get_lifestyle(profile.id)
    sports = await pref_repo.get_sports(profile.id)
    nutrition = await pref_repo.get_nutrition(profile.id)

    try:
        return CalculationService().calculate(
            profile, lifestyle, sports, nutrition, locale
        )
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("profile.missing_data_calc", locale),
        )


@router.get(
    "/{user_id}",
    response_model=ProfileResponse,
    dependencies=[Depends(verify_service_token)],
)
async def get_profile_for_service(
    request: Request,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Endpoint inter-service : retourne un profil par user_id. Authentifié par SERVICE_PROFILE_TOKEN."""
    locale = get_locale(request)
    profile = await ProfileService(session).get_by_user_id(user_id)
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale)
        )
    return ProfileResponse.model_validate(profile)
