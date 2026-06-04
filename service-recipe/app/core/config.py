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

    # Celery (import asynchrone de recettes). Queue dédiée "recipe" pour ne pas
    # être consommé par le worker d'un autre service partageant le broker Redis.
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "recipes"
    MINIO_PUBLIC_URL: str = "http://localhost:9000"

    SERVICE_NUTRITION_URL: str = ""
    SERVICE_NUTRITION_TOKEN: str = ""

    SERVICE_PROFILE_URL: str = "http://service-profile:8000"
    SERVICE_PROFILE_TOKEN: str = ""

    # service-notification : notification in-app de fin/échec d'import (best-effort).
    # Vide → notification ignorée (ex. en tests).
    SERVICE_NOTIFICATION_URL: str = ""
    SERVICE_NOTIFICATION_TOKEN: str = ""

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

    # Spoonacular (https://spoonacular.com/food-api) : récupération quotidienne de
    # recettes mises en cache. Auth par header "x-api-key". Vide → fetch désactivé
    # (no-op silencieux, pratique en tests / sans clé).
    SPOONACULAR_API_KEY: str = ""
    SPOONACULAR_API_URL: str = "https://api.spoonacular.com"
    # Nombre de recettes récupérées à chaque exécution (borné à 1..5 côté client).
    SPOONACULAR_DAILY_COUNT: int = 3
    # Heure (timezone Celery = Europe/Paris) du fetch quotidien via Celery beat.
    SPOONACULAR_FETCH_HOUR: int = 4
    # Traduction EN→FR des recettes au fetch (deep-translator/Google, sans clé).
    # Spoonacular ne renvoie que de l'anglais ; à False on garde l'anglais brut.
    SPOONACULAR_TRANSLATE: bool = True


settings = Settings()
