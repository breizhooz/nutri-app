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
    SERVICE_RECIPE_TOKEN: str = ""

    JS_DETECTION_THRESHOLD: int = 200

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "admin@nutriplanner.app"
    EXPO_PUSH_API_URL: str = "https://exp.host/--/api/v2/push/send"
    
settings = Settings()
