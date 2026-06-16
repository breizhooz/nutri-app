from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_CRAWLER: str
    S3_SECURE: bool = False

    SERVICE_RECIPE_URL: str
    SERVICE_RECIPE_TOKEN: str = ""

    SERVICE_NOTIFICATION_URL: str
    SERVICE_NOTIFICATION_TOKEN: str = ""

    SERVICE_NUTRITION_URL: str = ""
    SERVICE_NUTRITION_TOKEN: str = ""

    JS_DETECTION_THRESHOLD: int = 200

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    INSTAGRAM_USERNAME: str = ""
    INSTAGRAM_PASSWORD: str = ""
    INSTAGRAM_SESSION_FILE: str = "/data/instagram_session"
    # Anti-blocage Instagram : plafond de posts par run complet (0 = illimité),
    # tempo (s) toutes les INSTAGRAM_PAGE_SIZE posts + micro-tempo entre chaque
    # post, le tout bruité par INSTAGRAM_JITTER_RATIO (±ratio) pour casser la
    # périodicité détectable par Instagram et imiter un rythme humain.
    INSTAGRAM_MAX_POSTS_PER_RUN: int = 0
    INSTAGRAM_PAGE_DELAY_SECONDS: float = 2.0
    INSTAGRAM_PAGE_SIZE: int = 20
    INSTAGRAM_POST_DELAY_SECONDS: float = 0.8
    INSTAGRAM_JITTER_RATIO: float = 0.4

    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""  # comma-separated list; overrides GROQ_API_KEY when set
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_CONCURRENCY_PER_KEY: int = 2

    REDIS_CACHE_URL: str = "redis://redis:6379/2"
    GROQ_CACHE_TTL: int = 604800  # 7 days in seconds


settings = Settings()
