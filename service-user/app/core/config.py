"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for service-user.

    All values are loaded from environment variables or conf/.env.
    """

    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_BASE_URL: str = ""

    MFA_TOTP_ENCRYPTION_KEY: str = ""
    MFA_TOKEN_EXPIRE_MINUTES: int = 5
    MFA_EMAIL_CODE_EXPIRE_MINUTES: int = 5

    NOTIFICATION_SERVICE_URL: str = ""
    NOTIFICATION_SERVICE_TOKEN: str = ""


settings: Settings = Settings()