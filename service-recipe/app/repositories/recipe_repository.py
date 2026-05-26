from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ingredient import Ingredient
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient


class RecipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_with_relations(self, recipe_id: int) -> Recipe | None:
        result = await self.session.execute(
            select(Recipe)
            .where(Recipe.id == recipe_id)
            .options(
                selectinload(Recipe.recipe_ingredients).selectinload(
                    RecipeIngredient.ingredient
                )
            )
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: int | None = None) -> bool:
        q = select(Recipe.id).where(Recipe.slug == slug)
        if exclude_id is not None:
            q = q.where(Recipe.id != exclude_id)
        row = await self.session.execute(q)
        return row.scalar_one_or_none() is not None

    async def get_or_create_ingredient(self, name: str) -> Ingredient:
        result = await self.session.execute(
            select(Ingredient).where(Ingredient.name == name)
        )
        ingredient = result.scalar_one_or_none()
        if ingredient is None:
            ingredient = Ingredient(name=name)
            self.session.add(ingredient)
            await self.session.flush()
        return ingredient

    async def create(
        self, recipe: Recipe, recipe_ingredients: list[RecipeIngredient]
    ) -> Recipe:
        self.session.add(recipe)
        await self.session.flush()
        for ri in recipe_ingredients:
            ri.recipe_id = recipe.id
            self.session.add(ri)
        await self.session.commit()
        loaded = await self.get_by_id_with_relations(recipe.id)
        assert loaded is not None
        return loaded
