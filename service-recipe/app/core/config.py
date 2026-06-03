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

    SERVICE_PROFILE_URL: str = "http://service-profile:8000"
    SERVICE_PROFILE_TOKEN: str = ""

    # Active le scoring nutritionnel (proximité macros) dans la recherche.
    # L'index recettes porte désormais les champs macros (calories/proteines/
    # lipides/glucides) ; les fonctions de décroissance sont filtrées sur `exists`,
    # donc les recettes sans macro ne posent pas de problème.
    APPLY_NUTRITION_SCORING: bool = True

    # Unsplash : authentification "public/application-only" (header Client-ID).
    # Le SECRET_KEY n'est requis que pour le flux OAuth user (non utilisé ici), mais
    # on le provisionne pour un usage futur.
    UNSPLASH_ACCESS_KEY: str = ""
    UNSPLASH_SECRET_KEY: str = ""
    UNSPLASH_API_URL: str = "https://api.unsplash.com"

    # Nombre de propositions demandées à Unsplash par recherche. On en demande plus
    # que les 4 affichées par défaut : comme les résultats sont mis en cache
    # (table image_search_cache), le surcoût est amorti et l'utilisateur dispose de
    # davantage de choix lors d'un rafraîchissement.
    UNSPLASH_SUGGESTION_COUNT: int = 12
    # Durée de validité d'une entrée du cache d'images (jours). Passé ce délai, on
    # interroge à nouveau Unsplash pour rafraîchir les urls CDN.
    UNSPLASH_CACHE_TTL_DAYS: int = 30


settings = Settings()
