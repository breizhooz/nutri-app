"""
Import de recettes (+ catalogue d'ingrédients) depuis un fichier JSON.

Usage : python -m scripts.import_recipes <fichier.json>

Les macros (calories/protéines/glucides/lipides par portion) sont calculées
via service-nutrition : SERVICE_NUTRITION_URL doit pointer dessus (et
SERVICE_NUTRITION_TOKEN si l'endpoint /api/v1/calculate est protégé).
Format attendu : voir scripts/sample_recipes.json.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SERVICE_USER_URL", "http://service-user:8000")
os.environ.setdefault("ELASTICSEARCH_URL", "http://elasticsearch:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes")
os.environ.setdefault("JWT_SECRET", "import-secret")
os.environ.setdefault("SERVICE_NUTRITION_URL", "http://service-nutrition:8000")
os.environ.setdefault("SERVICE_NUTRITION_TOKEN", "")


def _load_payload(path: str):
    """Read and validate the JSON file. Exits with a clear message on error."""
    from pydantic import ValidationError
    from app.schemas.recipe_import import RecipeImportPayload

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print(f"Fichier introuvable : {path}")
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"JSON invalide ({path}) : {exc}")
        raise SystemExit(1)

    try:
        return RecipeImportPayload.model_validate(raw)
    except ValidationError as exc:
        print(f"Validation du fichier échouée :\n{exc}")
        raise SystemExit(1)


async def _run(path: str) -> None:
    payload = _load_payload(path)

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core import elasticsearch as es_module
    from app.core.elasticsearch import init_elasticsearch
    from app.repositories.recipe_repository import RecipeRepository
    from app.services.recipe_import_service import RecipeImportService
    from app.services.recipe_service import RecipeService
    from app.services.search_service import search_service

    es_ready = False
    try:
        await init_elasticsearch()
        es_ready = True
    except Exception as exc:
        print(
            f"Elasticsearch indisponible, indexation ignorée ({exc}). "
            "Lancez POST /api/v1/recipe/reindex plus tard."
        )

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            repository = RecipeRepository(session)
            recipe_service = RecipeService(repository, search_service)
            import_service = RecipeImportService(repository, recipe_service)
            report = await import_service.import_payload(payload)

        print(
            f"{report.ingredients_upserted} ingrédient(s) upsert(s), "
            f"{report.recipes_created} recette(s) créée(s)."
        )
        for slug in report.recipe_slugs:
            print(f"  - {slug}")
    finally:
        await engine.dispose()
        if es_ready and es_module.es_client is not None:
            await es_module.es_client.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python -m scripts.import_recipes <fichier.json>")
        raise SystemExit(1)
    asyncio.run(_run(sys.argv[1]))
