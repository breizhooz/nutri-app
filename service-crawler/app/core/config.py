from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = "conf/.env",
        extra="ignore"
    )

    DATABASE_URL: str
    DEBUG: bool = False

    CELERY_BROKER_URL: str 
    CELERY_RESULT_BACKEND: str

    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_CRAWLER: str
    MINIO_SECURE: bool = False

    SERVICE_RECIPE_URL: str

settings = Settings()