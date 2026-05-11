from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = "conf/.env",
        extra="ignore"
    )

    DATABASE_URL: str
    DEBUG: bool = False
    SERVICE_USER_URL: str = "http://service-user:8000"

    ELASTICSEARCH_URL: str
    ELASTICSEARCH_INDEX_RECIPES: str   
    
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

settings = Settings()