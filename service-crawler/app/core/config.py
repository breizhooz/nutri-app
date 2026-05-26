from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

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

    SERVICE_NOTIFICATION_URL: str
    SERVICE_NOTIFICATION_TOKEN: str = ""

    JS_DETECTION_THRESHOLD: int = 200

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    INSTAGRAM_USERNAME: str = ""
    INSTAGRAM_PASSWORD: str = ""
    INSTAGRAM_SESSION_FILE: str = "/data/instagram_session"

    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""  # comma-separated list; overrides GROQ_API_KEY when set
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_CONCURRENCY_PER_KEY: int = 2

    REDIS_CACHE_URL: str = "redis://redis:6379/2"
    GROQ_CACHE_TTL: int = 604800  # 7 days in seconds


settings = Settings()
