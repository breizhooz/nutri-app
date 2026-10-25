"""
Purge des recettes et des ingrédients.

Supprime toutes les lignes des tables recipe_ingredients, recipes et
ingredients (l'index plein texte vit dans la table recipes).

Usage : python -m scripts.drop_recipe [--yes]

  --yes / -y : ne demande pas de confirmation (utile en CI / scripts).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SERVICE_USER_URL", "http://service-user:8000")
os.environ.setdefault("JWT_SECRET", "drop-secret")
os.environ.setdefault("SERVICE_NUTRITION_URL", "")
os.environ.setdefault("SERVICE_NUTRITION_TOKEN", "")


def _confirm(skip: bool) -> bool:
    if skip:
        return True
    answer = input(
        "Cette opération supprime TOUTES les recettes et ingrédients. "
        "Confirmer ? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes", "o", "oui"}


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


if __name__ == "__main__":
    skip = any(arg in {"--yes", "-y"} for arg in sys.argv[1:])
    asyncio.run(_run(skip))
