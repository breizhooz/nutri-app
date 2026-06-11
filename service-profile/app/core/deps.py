"""Dépendances FastAPI partagées entre les routes."""

import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from nutri_shared.core.context import AccessContext, require_scope

from app.core.config import settings
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.profile_repository import ProfileRepository

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


def get_locale(request: Request) -> str:
    """Extrait la locale depuis le state injecté par LocaleMiddleware."""
    return getattr(getattr(request, "state", None), "locale", "fr")


async def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Extrait et valide l'UUID utilisateur depuis le JWT Bearer.

    Lève HTTP 401 si le token est absent, expiré ou malformé.
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        sub: str | None = payload.get("sub")
        if not sub:
            raise ValueError("sub manquant dans le token")
        user_id = uuid.UUID(sub)
        logger.debug("Token valide pour user_id=%s", user_id)
        return user_id
    except (InvalidTokenError, ValueError) as exc:
        logger.warning("Échec de validation du token : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t.get("errors.token_invalid", get_locale(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_service_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Vérifie le token inter-service pour les endpoints réservés aux autres MS.

    Lève HTTP 403 si le token ne correspond pas.
    """
    if credentials.credentials != settings.SERVICE_PROFILE_TOKEN:
        logger.warning("Tentative d'accès inter-service avec token invalide")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.service_token_invalid", get_locale(request)),
        )


# ── Multicomptes : contexte de compte + gardes de scope ──────────────────────
# Les routes /me* sont bornées par le compte actif (act_account du JWT). Le scope
# autorise l'action ; account_id borne le périmètre (cf. docs/roles/, phase 2).


def _account_uuid(request: Request, ctx: AccessContext) -> uuid.UUID:
    """Extrait l'UUID du compte actif. 403 si le token n'a pas de contexte."""
    if ctx.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.no_account_context", get_locale(request)),
        )
    return uuid.UUID(ctx.account_id)


async def get_read_account_id(
    request: Request,
    ctx: AccessContext = Depends(require_scope("profile:read")),
) -> uuid.UUID:
    """Compte actif pour une lecture du dossier (scope profile:read requis)."""
    return _account_uuid(request, ctx)


async def get_write_account_id(
    request: Request,
    ctx: AccessContext = Depends(require_scope("profile:write")),
) -> uuid.UUID:
    """Compte actif pour une écriture du dossier (scope profile:write requis)."""
    return _account_uuid(request, ctx)


async def get_write_context(
    request: Request,
    ctx: AccessContext = Depends(require_scope("profile:write")),
) -> AccessContext:
    """Contexte complet pour une écriture (compte + identité auteur).

    Utilisé par la création du dossier, qui a besoin de l'``account_id`` (clé de
    partition) ET du ``sub`` (auteur). Garantit un compte actif présent.
    """
    _account_uuid(request, ctx)  # 403 si pas de compte actif
    return ctx


async def _resolve_profile_id(
    request: Request, account_id: uuid.UUID, session: AsyncSession
) -> uuid.UUID:
    """Résout le profile_id du compte actif. 404 si le dossier n'existe pas."""
    profile = await ProfileRepository(session).get_by_account_id(account_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("profile.not_found", get_locale(request)),
        )
    return profile.id


async def read_profile_id(
    request: Request,
    account_id: uuid.UUID = Depends(get_read_account_id),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """profile_id du compte actif pour une lecture (sous-ressources du dossier)."""
    return await _resolve_profile_id(request, account_id, session)


async def write_profile_id(
    request: Request,
    account_id: uuid.UUID = Depends(get_write_account_id),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """profile_id du compte actif pour une écriture (sous-ressources du dossier)."""
    return await _resolve_profile_id(request, account_id, session)
