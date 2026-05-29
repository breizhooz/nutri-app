"""Cryptographic helpers: JWT creation, password hashing, MFA tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from nutri_shared.core.security import decode_token

__all__ = [
    "decode_token",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "create_mfa_token",
    "create_oauth_state",
    "verify_oauth_state",
]

_ph: PasswordHasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using Argon2id.

    Args:
        plain_password: The raw password to hash.

    Returns:
        An Argon2 hash string.
    """
    return _ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against an Argon2 hash.

    Args:
        plain_password: The raw password attempt.
        hashed_password: The stored Argon2 hash.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: str | Any, claims: dict[str, Any] | None = None
) -> str:
    """Create a short-lived JWT access token.

    Args:
        subject: The token subject, typically a user UUID string.
        claims: Optional extra claims (e.g. RBAC: user_admin, user_right) to
            embed so other services can authorize locally.

    Returns:
        A signed HS256 JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES
    )
    payload: dict = {"sub": str(subject), "exp": expire, "type": "access"}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | Any) -> str:
    """Create a long-lived JWT refresh token.

    Args:
        subject: The token subject, typically a user UUID string.

    Returns:
        A signed HS256 JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload: dict = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_mfa_token(subject: str | Any) -> str:
    """Create a short-lived JWT token for the MFA pending state.

    This token is issued after successful password verification when 2FA is
    enabled. It must be exchanged for a full token pair by calling /auth/2fa/verify.

    Args:
        subject: The user UUID string.

    Returns:
        A signed HS256 JWT string with type='mfa_pending'.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.MFA_TOKEN_EXPIRE_MINUTES
    )
    payload: dict = {"sub": str(subject), "exp": expire, "type": "mfa_pending"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_oauth_state(provider: str) -> str:
    """Create a short-lived JWT to use as the OAuth2 CSRF state parameter.

    Args:
        provider: The OAuth2 provider name ('google' or 'facebook').

    Returns:
        A signed HS256 JWT string with type='oauth_state'.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload: dict = {
        "provider": provider,
        "exp": expire,
        "type": "oauth_state",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_oauth_state(state: str) -> str:
    """Validate an OAuth2 state JWT and return the embedded provider.

    Args:
        state: The state JWT received in the OAuth2 callback query params.

    Returns:
        The provider name stored in the token.

    Raises:
        ValueError: If the token is invalid, expired, or has the wrong type.
    """
    try:
        payload = jwt.decode(
            state, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "oauth_state":
            raise ValueError("Invalid state token type")
        provider: str = payload["provider"]
        return provider
    except Exception as exc:
        raise ValueError("Invalid or expired OAuth state") from exc
