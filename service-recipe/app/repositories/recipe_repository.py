from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.image_cache import ImageSearchCache
from app.models.ingredient import Ingredient
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.schemas.recipe_import import IngredientImport
from app.schemas.recipe_ingredient import RecipeIngredientBase


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

    async def list_all_for_account(self, account_id: str) -> list[Recipe]:
        """Toutes les recettes d'un compte (vue bibliothèque, triées par titre)."""
        result = await self.session.execute(
            select(Recipe).where(Recipe.account_id == account_id).order_by(Recipe.title)
        )
        return list(result.scalars().all())

    async def find_clone(self, account_id: str, source_recipe_id: int) -> Recipe | None:
        """Recette déjà poussée d'une source donnée dans un compte (anti-doublon)."""
        result = await self.session.execute(
            select(Recipe).where(
                Recipe.account_id == account_id,
                Recipe.source_recipe_id == source_recipe_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug_with_relations(self, slug: str) -> Recipe | None:
        result = await self.session.execute(
            select(Recipe)
            .where(Recipe.slug == slug)
            .options(
                selectinload(Recipe.recipe_ingredients).selectinload(
                    RecipeIngredient.ingredient
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        course_type: str | None = None,
        account_id: str | None = None,
    ) -> tuple[list[Recipe], int]:
        """Return (items, total) for a page, optionally filtered.

        ``account_id`` borne la liste au compte actif (multicomptes).
        """
        base_query = select(Recipe)
        count_query = select(func.count()).select_from(Recipe)
        if course_type:
            base_query = base_query.where(Recipe.course_type == course_type)
            count_query = count_query.where(Recipe.course_type == course_type)
        if account_id:
            base_query = base_query.where(Recipe.account_id == account_id)
            count_query = count_query.where(Recipe.account_id == account_id)

        total = (await self.session.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            base_query.options(
                selectinload(Recipe.recipe_ingredients).selectinload(
                    RecipeIngredient.ingredient
                )
            )
            .order_by(Recipe.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def apply_update(
        self,
        recipe: Recipe,
        fields: dict,
        ingredients: list[RecipeIngredientBase] | None,
    ) -> Recipe:
        """Persist scalar field changes and optionally replace the ingredient set."""
        for field, value in fields.items():
            setattr(recipe, field, value)

        if ingredients is not None:
            await self.session.execute(
                delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
            )
            for ing in ingredients:
                self.session.add(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ing.ingredient_id,
                        quantity=ing.quantity,
                        unit=ing.unit,
                    )
                )

        await self.session.commit()
        loaded = await self.get_by_id_with_relations(recipe.id)
        assert loaded is not None
        return loaded

    async def delete(self, recipe: Recipe) -> None:
        await self.session.delete(recipe)
        await self.session.commit()

    async def delete_by_user(self, user_id: str) -> int:
        """Delete every recipe authored by ``user_id``. Returns rows removed.

        ``recipe_ingredients`` rows are removed by the database (FK
        ``ondelete=CASCADE``).
        """
        result = await self.session.execute(
            delete(Recipe).where(Recipe.created_by_user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount or 0

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

    async def upsert_ingredients(self, ingredients: list[IngredientImport]) -> int:
        """Create missing ingredients, refresh nutrition/tags of existing ones."""
        for data in ingredients:
            result = await self.session.execute(
                select(Ingredient).where(Ingredient.name == data.name)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                self.session.add(
                    Ingredient(
                        name=data.name,
                        tags=data.tags,
                        free_tags=data.free_tags,
                        calories_per_100g=data.calories_per_100g,
                        proteins_per_100g=data.proteins_per_100g,
                        carbs_per_100g=data.carbs_per_100g,
                        fats_per_100g=data.fats_per_100g,
                    )
                )
            else:
                existing.calories_per_100g = data.calories_per_100g
                existing.proteins_per_100g = data.proteins_per_100g
                existing.carbs_per_100g = data.carbs_per_100g
                existing.fats_per_100g = data.fats_per_100g
                if data.tags:
                    existing.tags = data.tags
                if data.free_tags:
                    existing.free_tags = data.free_tags
        await self.session.commit()
        return len(ingredients)

    async def update_image_url(self, recipe_id: int, image_url: str) -> Recipe:
        recipe = await self.session.get(Recipe, recipe_id)
        assert recipe is not None
        recipe.image_url = image_url
        await self.session.commit()
        loaded = await self.get_by_id_with_relations(recipe_id)
        assert loaded is not None
        return loaded

    async def update_image_suggestions(
        self, recipe_id: int, keyword: str, suggestions: list[dict]
    ) -> Recipe | None:
        recipe = await self.session.get(Recipe, recipe_id)
        if recipe is None:
            return None
        recipe.image_search_keyword = keyword
        recipe.image_suggestions = suggestions
        await self.session.commit()
        return await self.get_by_id_with_relations(recipe_id)

    async def get_cached_image_suggestions(
        self, keyword: str, fresh_after: datetime | None = None
    ) -> list[dict] | None:
        """Return cached Unsplash suggestions for a keyword matching ``keyword``,
        or ``None`` on a cache miss.

        Matching is **Postgres fulltext** (``to_tsvector('french', keyword) @@
        plainto_tsquery``) : stemming, stopwords and word order are ignored, but the
        meaningful lexemes must all be present. This deliberately excludes fuzzy
        cross-dish matches (e.g. two titles sharing only a boilerplate suffix like
        « version gourmande au beurre » must NOT collide). The best ``ts_rank`` wins;
        ``fresh_after`` excludes stale rows so the caller refetches.
        """
        tsv = func.to_tsvector("french", ImageSearchCache.keyword)
        tsq = func.plainto_tsquery("french", keyword)

        stmt = (
            select(ImageSearchCache.suggestions)
            .where(tsv.bool_op("@@")(tsq))
            .order_by(func.ts_rank(tsv, tsq).desc())
            .limit(1)
        )
        if fresh_after is not None:
            stmt = stmt.where(ImageSearchCache.updated_at >= fresh_after)

        suggestions = await self.session.scalar(stmt)
        return list(suggestions) if suggestions is not None else None

    async def upsert_cached_image_suggestions(
        self, keyword: str, suggestions: list[dict]
    ) -> None:
        """Insert or refresh the cached suggestions for ``keyword`` (normalized)."""
        row = await self.session.scalar(
            select(ImageSearchCache).where(ImageSearchCache.keyword == keyword)
        )
        if row is None:
            self.session.add(ImageSearchCache(keyword=keyword, suggestions=suggestions))
        else:
            row.suggestions = suggestions
        await self.session.commit()

    async def select_final_image(
        self, recipe_id: int, image_url: str, thumb_url: str | None
    ) -> Recipe | None:
        recipe = await self.session.get(Recipe, recipe_id)
        if recipe is None:
            return None
        recipe.image_url = image_url
        recipe.image_thumb_url = thumb_url
        await self.session.commit()
        return await self.get_by_id_with_relations(recipe_id)

    async def count_by_user(self) -> list[tuple[str, int]]:
        """Return (created_by_user_id, recipe_count) for every author."""
        result = await self.session.execute(
            select(Recipe.created_by_user_id, func.count())
            .where(Recipe.created_by_user_id.is_not(None))
            .group_by(Recipe.created_by_user_id)
        )
        return [(str(user_id), count) for user_id, count in result.all()]

    async def update_macros(
        self,
        recipe_id: int,
        calories: float,
        proteins: float,
        carbs: float,
        fats: float,
    ) -> None:
        recipe = await self.session.get(Recipe, recipe_id)
        if recipe is None:
            return
        recipe.calories_per_serving = calories
        recipe.proteins_per_serving = proteins
        recipe.carbs_per_serving = carbs
        recipe.fats_per_serving = fats
        await self.session.commit()

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
