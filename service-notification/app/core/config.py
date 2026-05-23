"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for service-notification."""

    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    VAPID_PRIVATE_KEY: str
    VAPID_PUBLIC_KEY: str
    VAPID_CLAIMS_EMAIL: str = "admin@nutriplanner.app"

    SERVICE_NOTIFICATION_TOKEN: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@nutri-app.com"
    SMTP_USE_TLS: bool = True


settings: Settings = Settings()