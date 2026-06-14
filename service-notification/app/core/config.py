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

    # Celery / Redis — purges de rétention RGPD (Phase 4)
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    # Rétention de l'historique des notifications : 12 mois (cf. docs/rgpd/retention.md)
    NOTIFICATION_RETENTION_DAYS: int = 365

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@nutri-app.com"
    SMTP_USE_TLS: bool = True


settings: Settings = Settings()
