import uuid

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums.enums import NutritionSource
from app.models.nutrition_item import NutritionItem


class NutritionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        nom_fr: str,
        calories: float,
        proteines: float,
        glucides: float,
        lipides: float,
        source: NutritionSource,
        nom_en: str | None = None,
        fibres: float | None = None,
        ciqual_id: str | None = None,
    ) -> NutritionItem:
        slug = await self._unique_slug(nom_fr)
        item = NutritionItem(
            slug=slug,
            nom_fr=nom_fr,
            nom_en=nom_en,
            calories=calories,
            proteines=proteines,
            glucides=glucides,
            lipides=lipides,
            fibres=fibres,
            source=source,
            ciqual_id=ciqual_id,
        )
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def get_by_slug(self, slug: str) -> NutritionItem | None:
        result = await self._session.execute(
            select(NutritionItem).where(NutritionItem.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_ciqual_id(self, ciqual_id: str) -> NutritionItem | None:
        result = await self._session.execute(
            select(NutritionItem).where(NutritionItem.ciqual_id == ciqual_id)
        )
        return result.scalar_one_or_none()

    async def update(self, item: NutritionItem, **kwargs) -> NutritionItem:
        for key, value in kwargs.items():
            setattr(item, key, value)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def _unique_slug(self, nom_fr: str) -> str:
        base = slugify(nom_fr)
        slug, counter = base, 2
        while await self.get_by_slug(slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug