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
    # Chiffrement at-rest (Fernet) des champs santé libres (notes médicales,
    # contre-indications). Lue par nutri_shared.db.encrypted.EncryptedText via
    # l'environnement. Générer avec Fernet.generate_key().
    PROFILE_FIELD_ENCRYPTION_KEY: str


settings = Settings()
