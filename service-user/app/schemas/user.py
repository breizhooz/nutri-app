"""Pydantic request/response schemas for user resources."""

import uuid

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """Payload for creating a new user with local email/password."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Enforce a minimum password length of 8 characters."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserOut(BaseModel):
    """Public representation of a user account."""

    id: uuid.UUID
    email: str
    is_active: bool
    two_factor_enabled: bool

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    """Credentials for the /login endpoint."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Full authentication token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class RefreshRequest(BaseModel):
    """Payload for the /auth/refresh endpoint."""

    refresh_token: str
