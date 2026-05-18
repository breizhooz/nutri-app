from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="conf/.env",
        extra="ignore",
    )

    DATABASE_URL: str
    DEBUG: bool = False

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    VAPID_PRIVATE_KEY: str
    VAPID_PUBLIC_KEY: str
    VAPID_CLAIMS_EMAIL: str = "admin@nutriplanner.app"

    # Token partagé avec les autres services pour les appels inter-services
    SERVICE_NOTIFICATION_TOKEN: str = ""


settings = Settings()