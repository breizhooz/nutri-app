"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for service-user.

    All values are loaded from environment variables or conf/.env.
    """

    model_config = SettingsConfigDict(env_file="conf/.env", extra="ignore")

    DATABASE_URL: str
    DEBUG: bool = False

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_BASE_URL: str = ""

    # Durée de vie du jeton de bootstrap OAuth (handoff callback → front → API).
    # Très court : il est consommé immédiatement après le retour du provider pour
    # poser le cookie refresh sur le bon hôte (cf. routes/oauth.py).
    OAUTH_BOOTSTRAP_TOKEN_EXPIRE_SECONDS: int = 60

    # Front SPA origin, used as the final redirect target of the OAuth callback.
    FRONTEND_URL: str = "https://localhost:5173"

    # SEC-05 : le refresh token n'est plus renvoyé en JSON mais posé dans un cookie
    # HttpOnly (inaccessible au JS → immunisé contre l'exfiltration par XSS).
    # En dev le front (localhost:5173) et l'API (api-users.localhost) sont des sites
    # différents → SameSite=None obligatoire pour que le cookie parte sur le XHR
    # /auth/refresh. Path restreint aux routes auth pour limiter la surface.
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "none"
    COOKIE_DOMAIN: str | None = None

    MFA_TOTP_ENCRYPTION_KEY: str = ""
    MFA_TOKEN_EXPIRE_MINUTES: int = 5
    MFA_EMAIL_CODE_EXPIRE_MINUTES: int = 5
    # Title shown in the authenticator app for TOTP entries (the QR issuer).
    MFA_ISSUER: str = "NutriPlanner"
    # Logo embedded at the centre of the 2FA QR code. Empty = bundled brand logo.
    MFA_QR_LOGO_PATH: str = ""

    NOTIFICATION_SERVICE_URL: str = ""
    NOTIFICATION_SERVICE_TOKEN: str = ""

    # ── Effacement RGPD (art. 17) — orchestration cross-service via Celery ──────
    # URL + token de service de chaque microservice détenant des données du
    # compte. Le token doit valoir le SERVICE_<X>_TOKEN attendu par la cible.
    # notification réutilise NOTIFICATION_SERVICE_URL / NOTIFICATION_SERVICE_TOKEN.
    PROFILE_SERVICE_URL: str = "http://service-profile:8000"
    PROFILE_SERVICE_TOKEN: str = ""
    MENU_SERVICE_URL: str = "http://service-menu:8000"
    MENU_SERVICE_TOKEN: str = ""
    NUTRITION_SERVICE_URL: str = "http://service-nutrition:8000"
    NUTRITION_SERVICE_TOKEN: str = ""

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Rétention (RGPD art. 5.1.e) — purges périodiques (Phase 4)
    AUDIT_LOG_RETENTION_DAYS: int = 1095  # ~3 ans
    INVITATION_RETENTION_DAYS: int = 90

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_BASE_URL: str = "http://localhost:3000"
    PASSWORD_HISTORY_COUNT: int = 5

    # SEC-07 : anti brute-force / credential stuffing. Fenêtre glissante par IP,
    # appliquée à /auth/login et /auth/2fa/verify. 0 = limitation désactivée.
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    MFA_VERIFY_RATE_LIMIT_PER_MINUTE: int = 10


settings: Settings = Settings()
