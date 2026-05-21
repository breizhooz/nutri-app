"""Dépendances FastAPI partagées entre les routes."""
import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


async def get_current_user_id(
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
    except (JWTError, ValueError) as exc:
        logger.warning("Échec de validation du token : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Vérifie le token inter-service pour les endpoints réservés aux autres MS.

    Lève HTTP 403 si le token ne correspond pas.
    """
    if credentials.credentials != settings.SERVICE_PROFILE_TOKEN:
        logger.warning("Tentative d'accès inter-service avec token invalide")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de service invalide",
        )


def get_locale(request: Request) -> str:
    """Extrait la locale depuis le state injecté par LocaleMiddleware."""
    return getattr(getattr(request, "state", None), "locale", "fr")