from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = "conf/.env",
        extra="ignore"
    )

    DATABASE_URL: str
    DEBUG: bool = False
    #
    # JWT_SECRET: str
    # JWT_ALGORITHM: str = "HS256"
    # JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    # JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

settings = Settings()