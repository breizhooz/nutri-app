from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"
    ELASTICSEARCH_INDEX: str = "nutrition_items"

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    OFF_BASE_URL: str = "https://world.openfoodfacts.org"
    OFF_USER_AGENT: str = "NutriPlanner/1.0 (contact@nutriplanner.fr)"

    CIQUAL_DOWNLOAD_URL: str = (
        "https://ciqual.anses.fr/cms/sites/default/files/inline-files/"
        "Table%20Ciqual%202020_FR_2020%2007%2007.zip"
    )
    CIQUAL_CACHE_PATH: str = "/tmp/ciqual.csv"

    SERVICE_NUTRITION_TOKEN: str = ""
    SERVICE_NOTIFICATION_URL: str = "http://service-notification:8006"
    SERVICE_NOTIFICATION_TOKEN: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()