"""Routes médicales : blessures, conditions, allergies, médicaments."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, get_locale
from app.db.session import get_session
from app.i18n import t
from app.repositories.profile_repository import ProfileRepository
from app.schemas.medical import (
    FoodAllergyCreate,
    FoodAllergyResponse,
    InjuryCreate,
    InjuryResponse,
    MedicalConditionCreate,
    MedicalConditionResponse,
    MedicationCreate,
    MedicationResponse,
)
from app.services.medical_service import MedicalService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_profile_id(user_id: uuid.UUID, session: AsyncSession, locale: str) -> uuid.UUID:
    """Résout le profile_id depuis le user_id. Lève 404 si le profil est absent."""
    profile = await ProfileRepository(session).get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale))
    return profile.id


@router.post("/me/injuries", response_model=InjuryResponse, status_code=status.HTTP_201_CREATED)
async def create_injury(
    request: Request,
    data: InjuryCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> InjuryResponse:
    """Enregistre une blessure pour le profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    result = await MedicalService(session).add_injury(profile_id, data)
    return InjuryResponse.model_validate(result)


@router.get("/me/injuries", response_model=list[InjuryResponse])
async def list_injuries(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[InjuryResponse]:
    """Retourne toutes les blessures du profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    results = await MedicalService(session).list_injuries(profile_id)
    return [InjuryResponse.model_validate(r) for r in results]


@router.delete("/me/injuries/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_injury(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une blessure par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await MedicalService(session).delete_injury(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("injury.not_found", locale))


@router.post("/me/conditions", response_model=MedicalConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    request: Request,
    data: MedicalConditionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MedicalConditionResponse:
    """Enregistre une condition médicale pour le profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    result = await MedicalService(session).add_condition(profile_id, data)
    return MedicalConditionResponse.model_validate(result)


@router.delete("/me/conditions/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une condition médicale par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await MedicalService(session).delete_condition(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("condition.not_found", locale))


@router.post("/me/allergies", response_model=FoodAllergyResponse, status_code=status.HTTP_201_CREATED)
async def create_allergy(
    request: Request,
    data: FoodAllergyCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> FoodAllergyResponse:
    """Enregistre une allergie alimentaire pour le profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    result = await MedicalService(session).add_allergy(profile_id, data)
    return FoodAllergyResponse.model_validate(result)


@router.get("/me/allergies", response_model=list[FoodAllergyResponse])
async def list_allergies(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[FoodAllergyResponse]:
    """Retourne toutes les allergies alimentaires du profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    results = await MedicalService(session).list_allergies(profile_id)
    return [FoodAllergyResponse.model_validate(r) for r in results]


@router.delete("/me/allergies/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allergy(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une allergie alimentaire par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await MedicalService(session).delete_allergy(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("allergy.not_found", locale))


@router.post("/me/medications", response_model=MedicationResponse, status_code=status.HTTP_201_CREATED)
async def create_medication(
    request: Request,
    data: MedicationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> MedicationResponse:
    """Enregistre un médicament pour le profil de l'utilisateur authentifié."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    result = await MedicalService(session).add_medication(profile_id, data)
    return MedicationResponse.model_validate(result)


@router.delete("/me/medications/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un médicament par son slug."""
    locale = get_locale(request)
    profile_id = await _get_profile_id(user_id, session, locale)
    if not await MedicalService(session).delete_medication(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("medication.not_found", locale))
