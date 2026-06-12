from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    SERVICE_USER_URL: str
    SERVICE_RECIPE_URL: str

    # Intégration service-profile (contraintes profil à la génération de menu).
    # Token vide = intégration désactivée : la génération fonctionne sans profil.
    SERVICE_PROFILE_URL: str = "http://service-profile:8000"
    SERVICE_PROFILE_TOKEN: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"


settings = Settings()
