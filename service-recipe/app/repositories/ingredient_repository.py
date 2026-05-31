from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredient import Ingredient


class IngredientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, ingredient_id: int) -> Ingredient | None:
        return await self.session.get(Ingredient, ingredient_id)

    async def get_by_name(self, name: str) -> Ingredient | None:
        result = await self.session.execute(
            select(Ingredient).where(Ingredient.name == name)
        )
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> list[Ingredient]:
        result = await self.session.execute(
            select(Ingredient).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, ingredient: Ingredient) -> Ingredient:
        self.session.add(ingredient)
        await self.session.commit()
        await self.session.refresh(ingredient)
        return ingredient

    async def update(self, ingredient: Ingredient, fields: dict) -> Ingredient:
        for field, value in fields.items():
            setattr(ingredient, field, value)
        await self.session.commit()
        await self.session.refresh(ingredient)
        return ingredient

    async def delete(self, ingredient: Ingredient) -> None:
        await self.session.delete(ingredient)
        await self.session.commit()
