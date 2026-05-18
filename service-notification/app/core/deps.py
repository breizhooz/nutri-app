import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import InvalidTokenError

from app.core.config import settings

_bearer = HTTPBearer()
_bearer_service = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Extrait l'UUID utilisateur depuis le JWT Bearer."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("sub manquant dans le token")
        return uuid.UUID(user_id)
    except (InvalidTokenError, ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_service),
) -> None:
    """Vérifie le token de service pour les appels inter-services."""
    if not settings.SERVICE_NOTIFICATION_TOKEN:
        # Token non configuré → pas de vérification (dev local)
        return
    if credentials.credentials != settings.SERVICE_NOTIFICATION_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de service invalide",
        )