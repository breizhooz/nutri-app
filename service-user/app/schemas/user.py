"""Pydantic request/response schemas for user resources."""

import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class CrawlRights(BaseModel):
    """Per-source crawl permissions (compte entier)."""

    instagram: bool = False
    web: bool = False


class UniqLinkRights(BaseModel):
    """Per-source single-link import permissions (oneshot par lien)."""

    instagram: bool = False
    web: bool = False


class UserRights(BaseModel):
    """Structured RBAC rights stored on the user."""

    crawl: CrawlRights = CrawlRights()
    uniq_link: UniqLinkRights = UniqLinkRights()


class UserCreate(BaseModel):
    """Payload for creating a new user with local email/password."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Enforce a minimum password length of 8 characters."""
        if len(v) < 8:
            raise ValueError("i18n:validation.password_too_short")
        return v


class UserOut(BaseModel):
    """Public representation of a user account, including RBAC rights."""

    id: uuid.UUID
    email: str
    is_active: bool
    two_factor_enabled: bool
    user_admin: bool = False
    user_right: dict = {}

    model_config = {"from_attributes": True}


class UserAdminOut(BaseModel):
    """User representation exposed in the admin management table."""

    id: uuid.UUID
    email: str
    is_active: bool
    user_admin: bool
    user_right: dict

    model_config = {"from_attributes": True}


class UserRightsUpdate(BaseModel):
    """Payload for an admin updating another user's RBAC rights.

    Both fields are optional so an admin can update one without the other.
    """

    user_admin: Optional[bool] = None
    user_right: Optional[UserRights] = None


class UserLogin(BaseModel):
    """Credentials for the /login endpoint."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Authentication response carrying the in-memory access token.

    SEC-05: the refresh token is no longer returned here — it is delivered as an
    HttpOnly cookie (see app/core/cookies.py).
    """

    access_token: str
    token_type: str = "Bearer"
