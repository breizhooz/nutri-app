from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spoonacular_cache import SpoonacularRecipeCache


class SpoonacularCacheRepository:
    """Accès BD au cache des recettes Spoonacular (upsert par ``spoonacular_id``)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        spoonacular_id: int,
        title: str,
        image_url: str | None,
        source_url: str | None,
        payload: dict,
    ) -> bool:
        """Insère ou rafraîchit une recette en cache.

        Retourne ``True`` si la ligne a été **créée**, ``False`` si elle existait
        déjà et a été mise à jour.
        """
        row = await self.session.scalar(
            select(SpoonacularRecipeCache).where(
                SpoonacularRecipeCache.spoonacular_id == spoonacular_id
            )
        )
        created = row is None
        if row is None:
            self.session.add(
                SpoonacularRecipeCache(
                    spoonacular_id=spoonacular_id,
                    title=title,
                    image_url=image_url,
                    source_url=source_url,
                    payload=payload,
                )
            )
        else:
            row.title = title
            row.image_url = image_url
            row.source_url = source_url
            row.payload = payload
        await self.session.commit()
        return created

    async def get_by_spoonacular_id(
        self, spoonacular_id: int
    ) -> SpoonacularRecipeCache | None:
        """Récupère une recette en cache par son id Spoonacular."""
        return await self.session.scalar(
            select(SpoonacularRecipeCache).where(
                SpoonacularRecipeCache.spoonacular_id == spoonacular_id
            )
        )

    async def get_random(self) -> SpoonacularRecipeCache | None:
        """Renvoie une recette du cache tirée au hasard (``None`` si vide)."""
        return await self.session.scalar(
            select(SpoonacularRecipeCache).order_by(func.random()).limit(1)
        )

    async def count(self) -> int:
        """Nombre total de recettes en cache."""
        return (
            await self.session.scalar(select(func.count(SpoonacularRecipeCache.id)))
            or 0
        )

    async def list_recent(self, limit: int = 20) -> list[SpoonacularRecipeCache]:
        """Dernières recettes mises en cache (plus récentes d'abord)."""
        rows = await self.session.scalars(
            select(SpoonacularRecipeCache)
            .order_by(SpoonacularRecipeCache.updated_at.desc())
            .limit(limit)
        )
        return list(rows)
