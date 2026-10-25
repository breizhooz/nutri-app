"""Profil nutritionnel du compte actif (préférences, exclusions, cibles).

Aucune donnée corporelle ni médicale : l'appareil garde poids/taille/âge/sexe et
ne transmet que les cibles calculées. Un champ inconnu (ex. ``weight_kg``) est
refusé (422). Écritures gardées par le consentement (RGPD art. 9 : le régime
peut révéler une conviction religieuse, les cibles restent sensibles).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_locale,
    get_read_account_id,
    get_write_account_id,
    require_health_consent,
)
from app.db.session import get_session
from app.i18n.loader import t
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
async def get_my_profile(
    request: Request,
    account_id: uuid.UUID = Depends(get_read_account_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileRead:
    profile = await ProfileService(session).get(account_id)
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=t.get("profile.not_found", get_locale(request)),
        )
    return ProfileRead.model_validate(profile)


@router.patch(
    "/me",
    response_model=ProfileRead,
    dependencies=[Depends(require_health_consent)],
)
async def update_my_profile(
    data: ProfileUpdate,
    account_id: uuid.UUID = Depends(get_write_account_id),
    session: AsyncSession = Depends(get_session),
) -> ProfileRead:
    """Crée ou met à jour (partiellement) le profil du compte actif."""
    profile = await ProfileService(session).upsert(account_id, data)
    return ProfileRead.model_validate(profile)
