"""Configuration centralisée via variables d'environnement."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres du service-profile lus depuis conf/.env."""

    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    SERVICE_PROFILE_TOKEN: str


settings = Settings()
