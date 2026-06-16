"""Routes du matériel de clés E2E zero-knowledge (Phase 3).

L'utilisateur connecté inscrit (une fois), consulte et fait tourner (au
changement de mot de passe) son enveloppe de clés opaque. Le serveur ne voit
jamais de secret. Cf. docs/rgpd/plan_dpo.md §1.
"""

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_locale
from app.db.session import get_session
from app.i18n.loader import t
from app.models.key_material import UserKeyMaterial
from app.models.user import User
from app.schemas.key_material import (
    KdfParams,
    KeyMaterialEnrollIn,
    KeyMaterialOut,
    KeyRotateIn,
    RecoveryMaterialOut,
    RecoveryRotateIn,
)
from app.services.key_material_service import (
    KeyMaterialAlreadyExists,
    KeyMaterialNotFound,
    KeyMaterialService,
)

router = APIRouter()


def _decode(request: Request, b64: str) -> bytes:
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("keys.material_invalid", get_locale(request)),
        )


def _params(material: UserKeyMaterial) -> KdfParams:
    return KdfParams(
        memory_mib=material.kdf_memory_mib,
        iterations=material.kdf_iterations,
        parallelism=material.kdf_parallelism,
    )


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


@router.get("/me/keys", response_model=KeyMaterialOut)
async def get_my_keys(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KeyMaterialOut:
    """Matériel pour dériver la MK et déchiffrer la UK sur cet appareil. 404 si non inscrit."""
    material = await KeyMaterialService(session).get(current_user.id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("keys.not_enrolled", get_locale(request)),
        )
    return KeyMaterialOut(
        salt=_b64(material.salt),
        kdf_params=_params(material),
        wrapped_uk=_b64(material.wrapped_uk),
    )


@router.post(
    "/me/keys", response_model=KeyMaterialOut, status_code=status.HTTP_201_CREATED
)
async def enroll_my_keys(
    request: Request,
    data: KeyMaterialEnrollIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KeyMaterialOut:
    """Inscrit le matériel de clés (une seule fois). 409 si déjà inscrit."""
    try:
        material = await KeyMaterialService(session).enroll(
            current_user.id,
            salt=_decode(request, data.salt),
            kdf_memory_mib=data.kdf_params.memory_mib,
            kdf_iterations=data.kdf_params.iterations,
            kdf_parallelism=data.kdf_params.parallelism,
            wrapped_uk=_decode(request, data.wrapped_uk),
            recovery_salt=_decode(request, data.recovery_salt),
            wrapped_uk_recovery=_decode(request, data.wrapped_uk_recovery),
        )
    except KeyMaterialAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("keys.already_enrolled", get_locale(request)),
        )
    return KeyMaterialOut(
        salt=_b64(material.salt),
        kdf_params=_params(material),
        wrapped_uk=_b64(material.wrapped_uk),
    )


@router.put("/me/keys", response_model=KeyMaterialOut)
async def rotate_my_keys(
    request: Request,
    data: KeyRotateIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> KeyMaterialOut:
    """Ré-enveloppe la UK après changement de mot de passe (blobs intacts). 404 si non inscrit."""
    try:
        material = await KeyMaterialService(session).rotate(
            current_user.id,
            salt=_decode(request, data.salt),
            kdf_memory_mib=data.kdf_params.memory_mib,
            kdf_iterations=data.kdf_params.iterations,
            kdf_parallelism=data.kdf_params.parallelism,
            wrapped_uk=_decode(request, data.wrapped_uk),
        )
    except KeyMaterialNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("keys.not_enrolled", get_locale(request)),
        )
    return KeyMaterialOut(
        salt=_b64(material.salt),
        kdf_params=_params(material),
        wrapped_uk=_b64(material.wrapped_uk),
    )


@router.put("/me/keys/recovery", response_model=RecoveryMaterialOut)
async def rotate_my_recovery(
    request: Request,
    data: RecoveryRotateIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecoveryMaterialOut:
    """Régénère le code de récupération (invalide l'ancien). 404 si non inscrit.

    La UK et le wrap par mot de passe sont inchangés (aucun blob re-chiffré) ;
    seule la voie de récupération est ré-enveloppée côté client.
    """
    try:
        material = await KeyMaterialService(session).rotate_recovery(
            current_user.id,
            recovery_salt=_decode(request, data.recovery_salt),
            wrapped_uk_recovery=_decode(request, data.wrapped_uk_recovery),
        )
    except KeyMaterialNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("keys.not_enrolled", get_locale(request)),
        )
    return RecoveryMaterialOut(
        recovery_salt=_b64(material.recovery_salt),
        kdf_params=_params(material),
        wrapped_uk_recovery=_b64(material.wrapped_uk_recovery),
    )


@router.get("/me/keys/recovery", response_model=RecoveryMaterialOut)
async def get_my_recovery_material(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecoveryMaterialOut:
    """Matériel pour déverrouiller la UK via le code de récupération. 404 si non inscrit."""
    material = await KeyMaterialService(session).get(current_user.id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("keys.not_enrolled", get_locale(request)),
        )
    return RecoveryMaterialOut(
        recovery_salt=_b64(material.recovery_salt),
        kdf_params=_params(material),
        wrapped_uk_recovery=_b64(material.wrapped_uk_recovery),
    )
