import os

# Must be set before any app module is imported
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SERVICE_USER_URL", "http://service-user-test:8000")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("ELASTICSEARCH_URL", "http://elasticsearch-test:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes-test")
