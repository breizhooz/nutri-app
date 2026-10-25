"""Suppression d'une recette chargée AVEC ses ingrédients (vraie base SQLite).

Régression : sans ``cascade="all, delete-orphan"`` sur ``Recipe.recipe_ingredients``,
l'ORM « détachait » les lignes enfants chargées en mettant ``recipe_id`` à NULL
→ violation NOT NULL → ``DELETE /recipe/id/{id}`` en 500.

Seules les tables ``recipes`` et ``recipe_ingredients`` sont créées : la table
``ingredients`` utilise un ARRAY PostgreSQL (non supporté par SQLite) et n'est
pas nécessaire ici (SQLite ne vérifie pas la cible des clés étrangères).
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.repositories.recipe_repository import RecipeRepository


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Recipe.metadata.create_all(
                sync_conn, tables=[Recipe.__table__, RecipeIngredient.__table__]
            )
        )
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _count(session: AsyncSession, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar()


def test_relationship_cascades_deletes_to_ingredient_lines():
    cascade = Recipe.recipe_ingredients.property.cascade
    assert cascade.delete and cascade.delete_orphan


async def test_delete_recipe_with_loaded_ingredients(session):
    recipe = Recipe(title="Pâtes à l'ail", slug="pates-a-l-ail", instructions="Cuire.")
    session.add(recipe)
    await session.flush()
    session.add_all(
        [
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=1, quantity=200, unit="g"
            ),
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=2, quantity=3, unit="gousse"
            ),
        ]
    )
    await session.commit()
    session.expunge_all()

    # Chargée comme le fait la route (ingrédients en selectinload).
    loaded = (
        await session.execute(
            select(Recipe)
            .options(selectinload(Recipe.recipe_ingredients))
            .where(Recipe.id == recipe.id)
        )
    ).scalar_one()
    assert len(loaded.recipe_ingredients) == 2

    await RecipeRepository(session).delete(loaded)

    assert await _count(session, Recipe) == 0
    assert await _count(session, RecipeIngredient) == 0
