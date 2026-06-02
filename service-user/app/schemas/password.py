"""Pydantic schemas for the password reset workflow."""

from pydantic import BaseModel, EmailStr, field_validator


class PasswordResetRequestSchema(BaseModel):
    """Payload for POST /api/v1/auth/password/reset-request."""

    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    """Payload for POST /api/v1/auth/password/reset."""

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("i18n:validation.password_too_short")
        return v


class PasswordChangeSchema(BaseModel):
    """Payload for POST /api/v1/users/me/password — authenticated password change."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("i18n:validation.password_too_short")
        return v


class PasswordResetMessage(BaseModel):
    """Generic response message for password reset endpoints."""

    message: str
