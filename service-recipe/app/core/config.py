from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    SERVICE_USER_URL: str = "http://service-user:8000"

    ELASTICSEARCH_URL: str
    ELASTICSEARCH_INDEX_RECIPES: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "recipes"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"

    SERVICE_NUTRITION_URL: str = ""
    SERVICE_NUTRITION_TOKEN: str = ""

    # Unsplash : authentification "public/application-only" (header Client-ID).
    # Le SECRET_KEY n'est requis que pour le flux OAuth user (non utilisé ici), mais
    # on le provisionne pour un usage futur.
    UNSPLASH_ACCESS_KEY: str = ""
    UNSPLASH_SECRET_KEY: str = ""
    UNSPLASH_API_URL: str = "https://api.unsplash.com"


settings = Settings()
