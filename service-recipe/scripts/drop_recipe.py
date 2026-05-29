"""
Purge des recettes et des ingrédients.

Supprime toutes les lignes des tables recipe_ingredients, recipes et
ingredients, puis remet à zéro l'index Elasticsearch des recettes.

Usage : python -m scripts.drop_recipe [--yes]

  --yes / -y : ne demande pas de confirmation (utile en CI / scripts).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SERVICE_USER_URL", "http://service-user:8000")
os.environ.setdefault("ELASTICSEARCH_URL", "http://elasticsearch:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes")
os.environ.setdefault("JWT_SECRET", "drop-secret")
os.environ.setdefault("SERVICE_NUTRITION_URL", "")
os.environ.setdefault("SERVICE_NUTRITION_TOKEN", "")


def _confirm(skip: bool) -> bool:
    if skip:
        return True
    answer = input(
        "Cette opération supprime TOUTES les recettes et ingrédients "
        "(DB + index Elasticsearch). Confirmer ? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes", "o", "oui"}


async def _reset_elasticsearch() -> None:
    """Drop puis recrée l'index des recettes (mapping conservé)."""
    from app.core import elasticsearch as es_module
    from app.core.config import settings
    from app.core.elasticsearch import init_elasticsearch

    index_name = settings.ELASTICSEARCH_INDEX_RECIPES
    try:
        await init_elasticsearch()
        await es_module.es_client.indices.delete(
            index=index_name, ignore_unavailable=True
        )
        # Recrée l'index vide avec le mapping à jour.
        await init_elasticsearch()
        print(f"Index Elasticsearch '{index_name}' réinitialisé.")
    except Exception as exc:
        print(
            f"Elasticsearch indisponible, index non nettoyé ({exc}). "
            "Relancez POST /api/v1/recipe/reindex ou ce script plus tard."
        )
    finally:
        if es_module.es_client is not None:
            await es_module.es_client.close()


async def _drop_db() -> tuple[int, int, int]:
    from sqlalchemy import delete, func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models.ingredient import Ingredient
    from app.models.recipe import Recipe
    from app.models.recipe_ingredients import RecipeIngredient

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            recipes = await session.scalar(select(func.count()).select_from(Recipe))
            ingredients = await session.scalar(
                select(func.count()).select_from(Ingredient)
            )
            links = await session.scalar(
                select(func.count()).select_from(RecipeIngredient)
            )

            # Ordre de suppression : table de liaison d'abord (FK sans cascade
            # côté ingredient), puis recettes, puis ingrédients.
            await session.execute(delete(RecipeIngredient))
            await session.execute(delete(Recipe))
            await session.execute(delete(Ingredient))
            await session.commit()
        return recipes, ingredients, links
    finally:
        await engine.dispose()


async def _run(skip_confirm: bool) -> None:
    if not _confirm(skip_confirm):
        print("Annulé.")
        return

    recipes, ingredients, links = await _drop_db()
    print(
        f"DB purgée : {recipes} recette(s), {ingredients} ingrédient(s), "
        f"{links} association(s) recette-ingrédient supprimée(s)."
    )

    await _reset_elasticsearch()


if __name__ == "__main__":
    skip = any(arg in {"--yes", "-y"} for arg in sys.argv[1:])
    asyncio.run(_run(skip))
