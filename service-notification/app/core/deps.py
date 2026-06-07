import hmac
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.i18n.loader import t

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
            detail=t.get("errors.token_invalid"),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_service),
) -> None:
    """Vérifie le token de service pour les appels inter-services.

    SEC-06 : fail-closed — si le token n'est pas configuré, on refuse l'accès
    (503) au lieu d'ouvrir l'endpoint. Comparaison à temps constant pour ne pas
    fuiter le secret via une attaque temporelle.
    """
    if not settings.SERVICE_NOTIFICATION_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t.get("errors.service_token_invalid"),
        )
    if not hmac.compare_digest(
        credentials.credentials, settings.SERVICE_NOTIFICATION_TOKEN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.service_token_invalid"),
        )
