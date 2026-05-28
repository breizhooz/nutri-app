"""
Seed de base des ingrédients courants.
Usage : python -m scripts.seed_ingredients
Guard : n'insère rien si la table contient déjà des entrées (premier démarrage only).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
os.environ.setdefault("SERVICE_USER_URL", "http://service-user:8000")
os.environ.setdefault("ELASTICSEARCH_URL", "http://elasticsearch:9200")
os.environ.setdefault("ELASTICSEARCH_INDEX_RECIPES", "recipes")
os.environ.setdefault("JWT_SECRET", "seed-secret")
os.environ.setdefault("SERVICE_NUTRITION_URL", "")
os.environ.setdefault("SERVICE_NUTRITION_TOKEN", "")

INGREDIENTS: list[dict] = [
    # ── Crudités ──────────────────────────────────────────
    {
        "name": "carottes",
        "calories_per_100g": 41.0,
        "proteins_per_100g": 0.9,
        "carbs_per_100g": 9.6,
        "fats_per_100g": 0.2,
    },
    {
        "name": "concombre",
        "calories_per_100g": 15.0,
        "proteins_per_100g": 0.7,
        "carbs_per_100g": 3.6,
        "fats_per_100g": 0.1,
    },
    {
        "name": "tomates",
        "calories_per_100g": 18.0,
        "proteins_per_100g": 0.9,
        "carbs_per_100g": 3.5,
        "fats_per_100g": 0.2,
    },
    {
        "name": "courgettes",
        "calories_per_100g": 17.0,
        "proteins_per_100g": 1.2,
        "carbs_per_100g": 3.1,
        "fats_per_100g": 0.3,
    },
    {
        "name": "poivrons rouges",
        "calories_per_100g": 31.0,
        "proteins_per_100g": 1.0,
        "carbs_per_100g": 6.0,
        "fats_per_100g": 0.3,
    },
    {
        "name": "céleri",
        "calories_per_100g": 16.0,
        "proteins_per_100g": 0.7,
        "carbs_per_100g": 3.0,
        "fats_per_100g": 0.2,
    },
    {
        "name": "radis",
        "calories_per_100g": 16.0,
        "proteins_per_100g": 0.7,
        "carbs_per_100g": 3.4,
        "fats_per_100g": 0.1,
    },
    {
        "name": "épinards",
        "calories_per_100g": 23.0,
        "proteins_per_100g": 2.9,
        "carbs_per_100g": 3.6,
        "fats_per_100g": 0.4,
    },
    {
        "name": "salade verte",
        "calories_per_100g": 13.0,
        "proteins_per_100g": 1.4,
        "carbs_per_100g": 1.8,
        "fats_per_100g": 0.2,
    },
    {
        "name": "brocoli",
        "calories_per_100g": 34.0,
        "proteins_per_100g": 2.8,
        "carbs_per_100g": 6.6,
        "fats_per_100g": 0.4,
    },
    {
        "name": "chou-fleur",
        "calories_per_100g": 25.0,
        "proteins_per_100g": 1.9,
        "carbs_per_100g": 5.0,
        "fats_per_100g": 0.3,
    },
    {
        "name": "oignons",
        "calories_per_100g": 40.0,
        "proteins_per_100g": 1.1,
        "carbs_per_100g": 9.3,
        "fats_per_100g": 0.1,
    },
    {
        "name": "ail",
        "calories_per_100g": 149.0,
        "proteins_per_100g": 6.4,
        "carbs_per_100g": 33.1,
        "fats_per_100g": 0.5,
    },
    # ── Fruits ────────────────────────────────────────────
    {
        "name": "pommes",
        "calories_per_100g": 52.0,
        "proteins_per_100g": 0.3,
        "carbs_per_100g": 13.8,
        "fats_per_100g": 0.2,
    },
    {
        "name": "poires",
        "calories_per_100g": 57.0,
        "proteins_per_100g": 0.4,
        "carbs_per_100g": 15.2,
        "fats_per_100g": 0.1,
    },
    {
        "name": "raisins",
        "calories_per_100g": 67.0,
        "proteins_per_100g": 0.6,
        "carbs_per_100g": 17.2,
        "fats_per_100g": 0.2,
    },
    {
        "name": "bananes",
        "calories_per_100g": 89.0,
        "proteins_per_100g": 1.1,
        "carbs_per_100g": 22.8,
        "fats_per_100g": 0.3,
    },
    {
        "name": "oranges",
        "calories_per_100g": 47.0,
        "proteins_per_100g": 0.9,
        "carbs_per_100g": 11.8,
        "fats_per_100g": 0.1,
    },
    {
        "name": "fraises",
        "calories_per_100g": 32.0,
        "proteins_per_100g": 0.7,
        "carbs_per_100g": 7.7,
        "fats_per_100g": 0.3,
    },
    {
        "name": "kiwis",
        "calories_per_100g": 61.0,
        "proteins_per_100g": 1.1,
        "carbs_per_100g": 14.7,
        "fats_per_100g": 0.5,
    },
    {
        "name": "abricots",
        "calories_per_100g": 48.0,
        "proteins_per_100g": 1.4,
        "carbs_per_100g": 11.1,
        "fats_per_100g": 0.4,
    },
    {
        "name": "pêches",
        "calories_per_100g": 39.0,
        "proteins_per_100g": 0.9,
        "carbs_per_100g": 9.5,
        "fats_per_100g": 0.3,
    },
    {
        "name": "myrtilles",
        "calories_per_100g": 57.0,
        "proteins_per_100g": 0.7,
        "carbs_per_100g": 14.5,
        "fats_per_100g": 0.3,
    },
    # ── Laitages ──────────────────────────────────────────
    {
        "name": "petits suisses",
        "calories_per_100g": 101.0,
        "proteins_per_100g": 7.8,
        "carbs_per_100g": 3.6,
        "fats_per_100g": 6.4,
    },
    {
        "name": "yaourt nature",
        "calories_per_100g": 59.0,
        "proteins_per_100g": 3.5,
        "carbs_per_100g": 4.7,
        "fats_per_100g": 3.0,
    },
    {
        "name": "lait entier",
        "calories_per_100g": 61.0,
        "proteins_per_100g": 3.2,
        "carbs_per_100g": 4.8,
        "fats_per_100g": 3.3,
    },
    {
        "name": "fromage blanc",
        "calories_per_100g": 77.0,
        "proteins_per_100g": 7.3,
        "carbs_per_100g": 3.0,
        "fats_per_100g": 4.0,
    },
    {
        "name": "beurre",
        "calories_per_100g": 717.0,
        "proteins_per_100g": 0.9,
        "carbs_per_100g": 0.1,
        "fats_per_100g": 81.0,
    },
    {
        "name": "gruyère râpé",
        "calories_per_100g": 413.0,
        "proteins_per_100g": 29.8,
        "carbs_per_100g": 0.4,
        "fats_per_100g": 32.3,
    },
    # ── Féculents ─────────────────────────────────────────
    {
        "name": "pâtes",
        "calories_per_100g": 350.0,
        "proteins_per_100g": 12.5,
        "carbs_per_100g": 70.0,
        "fats_per_100g": 1.5,
    },
    {
        "name": "riz",
        "calories_per_100g": 356.0,
        "proteins_per_100g": 6.7,
        "carbs_per_100g": 79.0,
        "fats_per_100g": 0.7,
    },
    {
        "name": "pommes de terre",
        "calories_per_100g": 77.0,
        "proteins_per_100g": 2.0,
        "carbs_per_100g": 17.5,
        "fats_per_100g": 0.1,
    },
    {
        "name": "pain de mie",
        "calories_per_100g": 265.0,
        "proteins_per_100g": 8.0,
        "carbs_per_100g": 50.0,
        "fats_per_100g": 3.5,
    },
    # ── Protéines ─────────────────────────────────────────
    {
        "name": "oeufs",
        "calories_per_100g": 143.0,
        "proteins_per_100g": 13.0,
        "carbs_per_100g": 1.1,
        "fats_per_100g": 9.5,
    },
    {
        "name": "poulet (filet)",
        "calories_per_100g": 165.0,
        "proteins_per_100g": 31.0,
        "carbs_per_100g": 0.0,
        "fats_per_100g": 3.6,
    },
    {
        "name": "saumon",
        "calories_per_100g": 208.0,
        "proteins_per_100g": 20.0,
        "carbs_per_100g": 0.0,
        "fats_per_100g": 13.0,
    },
    {
        "name": "thon en boîte",
        "calories_per_100g": 116.0,
        "proteins_per_100g": 25.5,
        "carbs_per_100g": 0.0,
        "fats_per_100g": 1.0,
    },
    # ── Huiles & condiments ───────────────────────────────
    {
        "name": "huile d'olive",
        "calories_per_100g": 884.0,
        "proteins_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "fats_per_100g": 100.0,
    },
    {
        "name": "sel",
        "calories_per_100g": 0.0,
        "proteins_per_100g": 0.0,
        "carbs_per_100g": 0.0,
        "fats_per_100g": 0.0,
    },
    {
        "name": "poivre",
        "calories_per_100g": 251.0,
        "proteins_per_100g": 10.4,
        "carbs_per_100g": 64.0,
        "fats_per_100g": 3.3,
    },
]


async def _seed() -> None:
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    from app.models.ingredient import Ingredient

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            count_result = await session.execute(
                select(func.count()).select_from(Ingredient)
            )
            count = count_result.scalar_one()
            if count > 0:
                print(f"Table déjà peuplée ({count} ingrédients) — seed ignoré.")
                return

            for data in INGREDIENTS:
                existing = await session.execute(
                    select(Ingredient).where(Ingredient.name == data["name"])
                )
                if existing.scalar_one_or_none():
                    continue
                session.add(
                    Ingredient(
                        name=data["name"],
                        calories_per_100g=data.get("calories_per_100g"),
                        proteins_per_100g=data.get("proteins_per_100g"),
                        carbs_per_100g=data.get("carbs_per_100g"),
                        fats_per_100g=data.get("fats_per_100g"),
                    )
                )

            await session.commit()
            print(f"{len(INGREDIENTS)} ingrédients seedés avec succès.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_seed())
