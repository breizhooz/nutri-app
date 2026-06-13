"""Routes médicales : blessures, conditions, allergies, médicaments.

Bornées par le compte actif (multicomptes) : ``read_profile_id`` /
``write_profile_id`` résolvent le dossier via ``act_account`` et enforcent le
scope ``profile:read`` / ``profile:write``.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_locale,
    read_profile_id,
    require_health_consent,
    write_profile_id,
)
from app.db.session import get_session
from app.i18n import t
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


@router.post(
    "/me/injuries", response_model=InjuryResponse, status_code=status.HTTP_201_CREATED
)
async def create_injury(
    data: InjuryCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    _consent: None = Depends(require_health_consent),  # RGPD art. 9
    session: AsyncSession = Depends(get_session),
) -> InjuryResponse:
    """Enregistre une blessure pour le dossier du compte actif."""
    result = await MedicalService(session).add_injury(profile_id, data)
    return InjuryResponse.model_validate(result)


@router.get("/me/injuries", response_model=list[InjuryResponse])
async def list_injuries(
    profile_id: uuid.UUID = Depends(read_profile_id),
    session: AsyncSession = Depends(get_session),
) -> list[InjuryResponse]:
    """Retourne toutes les blessures du dossier du compte actif."""
    results = await MedicalService(session).list_injuries(profile_id)
    return [InjuryResponse.model_validate(r) for r in results]


@router.delete("/me/injuries/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_injury(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une blessure par son slug."""
    locale = get_locale(request)
    if not await MedicalService(session).delete_injury(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("injury.not_found", locale)
        )


@router.post(
    "/me/conditions",
    response_model=MedicalConditionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_condition(
    data: MedicalConditionCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    _consent: None = Depends(require_health_consent),  # RGPD art. 9
    session: AsyncSession = Depends(get_session),
) -> MedicalConditionResponse:
    """Enregistre une condition médicale pour le dossier du compte actif."""
    result = await MedicalService(session).add_condition(profile_id, data)
    return MedicalConditionResponse.model_validate(result)


@router.delete("/me/conditions/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une condition médicale par son slug."""
    locale = get_locale(request)
    if not await MedicalService(session).delete_condition(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("condition.not_found", locale)
        )


@router.post(
    "/me/allergies",
    response_model=FoodAllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_allergy(
    data: FoodAllergyCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    _consent: None = Depends(require_health_consent),  # RGPD art. 9
    session: AsyncSession = Depends(get_session),
) -> FoodAllergyResponse:
    """Enregistre une allergie alimentaire pour le dossier du compte actif."""
    result = await MedicalService(session).add_allergy(profile_id, data)
    return FoodAllergyResponse.model_validate(result)


@router.get("/me/allergies", response_model=list[FoodAllergyResponse])
async def list_allergies(
    profile_id: uuid.UUID = Depends(read_profile_id),
    session: AsyncSession = Depends(get_session),
) -> list[FoodAllergyResponse]:
    """Retourne toutes les allergies alimentaires du dossier du compte actif."""
    results = await MedicalService(session).list_allergies(profile_id)
    return [FoodAllergyResponse.model_validate(r) for r in results]


@router.delete("/me/allergies/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allergy(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime une allergie alimentaire par son slug."""
    locale = get_locale(request)
    if not await MedicalService(session).delete_allergy(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("allergy.not_found", locale)
        )


@router.post(
    "/me/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_medication(
    data: MedicationCreate,
    profile_id: uuid.UUID = Depends(write_profile_id),
    _consent: None = Depends(require_health_consent),  # RGPD art. 9
    session: AsyncSession = Depends(get_session),
) -> MedicationResponse:
    """Enregistre un médicament pour le dossier du compte actif."""
    result = await MedicalService(session).add_medication(profile_id, data)
    return MedicationResponse.model_validate(result)


@router.delete("/me/medications/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    request: Request,
    slug: str,
    profile_id: uuid.UUID = Depends(write_profile_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Supprime un médicament par son slug."""
    locale = get_locale(request)
    if not await MedicalService(session).delete_medication(slug, profile_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=t.get("medication.not_found", locale)
        )
