import uuid
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.core.security import decode_token
from app.i18n.loader import t

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
            detail=t.get("errors.token_invalid"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user_id(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> uuid.UUID:
    """Extrait le user_id depuis le payload validé."""
    return uuid.UUID(str(payload["sub"]))


def _has_right(payload: dict[str, Any], group: str, source: str) -> bool:
    """True si le token porte le droit ``group.source`` (admin = bypass)."""
    if payload.get("user_admin"):
        return True
    group_rights = (payload.get("user_right") or {}).get(group) or {}
    return bool(group_rights.get(source))


class CrawlPermission:
    """Autorisation de crawl d'un compte entier (``user_right.crawl.{source}``)."""

    @staticmethod
    def allowed(payload: dict[str, Any], source: str) -> bool:
        return _has_right(payload, "crawl", source)

    @staticmethod
    def ensure(payload: dict[str, Any], source: str) -> None:
        """Lève 403 si l'utilisateur n'a pas le droit de crawl pour ``source``."""
        if not CrawlPermission.allowed(payload, source):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=t.get("errors.crawl_not_allowed", source=source),
            )


class UniqLinkPermission:
    """Autorisation d'import par lien unique (``user_right.uniq_link.{source}``)."""

    @staticmethod
    def allowed(payload: dict[str, Any], source: str) -> bool:
        return _has_right(payload, "uniq_link", source)

    @staticmethod
    def ensure(payload: dict[str, Any], source: str) -> None:
        """Lève 403 si l'utilisateur n'a pas le droit d'import par lien ``source``."""
        if not UniqLinkPermission.allowed(payload, source):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=t.get("errors.uniq_link_not_allowed", source=source),
            )


async def require_admin(
    payload: dict[str, Any] = Depends(get_token_payload),
) -> dict[str, Any]:
    """Exige le claim ``user_admin`` ; lève 403 sinon. Renvoie le payload."""
    if not payload.get("user_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.admin_only"),
        )
    return payload


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
