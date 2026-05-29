import uuid
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.core.security import decode_token

bearer_scheme = HTTPBearer()


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Décode et valide l'access JWT, renvoie le payload complet.

    Le payload porte les claims RBAC (``user_admin``, ``user_right``) posés par
    service-user — autorisation locale, aucun appel réseau nécessaire.
    """
    try:
        payload = decode_token(credentials.credentials)
        token_type = payload.get("type")
        user_id: str | None = payload.get("sub")
        if not user_id or token_type != "access":  # nosec B105
            raise InvalidTokenError("sub manquant ou type de token invalide")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> uuid.UUID:
    """Extrait le user_id depuis le payload validé."""
    return uuid.UUID(str(payload["sub"]))


class CrawlPermission:
    """Règles d'autorisation de crawl basées sur les claims RBAC du token."""

    @staticmethod
    def allowed(payload: dict[str, Any], source: str) -> bool:
        """True si l'utilisateur peut crawler ce type de source (admin = bypass)."""
        if payload.get("user_admin"):
            return True
        crawl_rights = (payload.get("user_right") or {}).get("crawl") or {}
        return bool(crawl_rights.get(source))

    @staticmethod
    def ensure(payload: dict[str, Any], source: str) -> None:
        """Lève 403 si l'utilisateur n'a pas le droit de crawl pour ``source``."""
        if not CrawlPermission.allowed(payload, source):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Crawl '{source}' non autorisé",
            )


class RequireCrawlRight:
    """Dépendance paramétrable : exige le droit de crawl d'un type de source fixe.

    Renvoie le user_id pour rester interchangeable avec get_current_user_id.
    """

    def __init__(self, source: str) -> None:
        self.source = source

    async def __call__(
        self, payload: dict[str, Any] = Depends(get_token_payload)
    ) -> uuid.UUID:
        CrawlPermission.ensure(payload, self.source)
        return uuid.UUID(str(payload["sub"]))
