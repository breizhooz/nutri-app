import uuid
from datetime import datetime, timezone

from slugify import slugify
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums.enums import MacroErrorStatus
from app.models.macro_error import MacroError


class MacroErrorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        raw_ingredient: str,
        recipe_id: uuid.UUID | None = None,
        suggested_match: str | None = None,
        match_score: float | None = None,
    ) -> MacroError:
        slug = self._build_slug(raw_ingredient)
        error = MacroError(
            slug=slug,
            user_id=user_id,
            recipe_id=recipe_id,
            raw_ingredient=raw_ingredient,
            suggested_match=suggested_match,
            match_score=match_score,
            status=MacroErrorStatus.PENDING,
        )
        self._session.add(error)
        await self._session.commit()
        await self._session.refresh(error)
        return error

    async def get_by_slug(self, slug: str) -> MacroError | None:
        result = await self._session.execute(
            select(MacroError).where(MacroError.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: uuid.UUID,
        status: MacroErrorStatus | None = None,
    ) -> list[MacroError]:
        q = select(MacroError).where(MacroError.user_id == user_id)
        if status is not None:
            q = q.where(MacroError.status == status)
        q = q.order_by(MacroError.created_at.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def resolve(
        self,
        error: MacroError,
        resolved_name: str,
        calories: float | None = None,
        proteines: float | None = None,
        glucides: float | None = None,
        lipides: float | None = None,
    ) -> MacroError:
        has_manual_macros = calories is not None
        error.status = MacroErrorStatus.MANUAL if has_manual_macros else MacroErrorStatus.RESOLVED
        error.resolved_name = resolved_name
        error.calories_manual = calories
        error.proteines_manual = proteines
        error.glucides_manual = glucides
        error.lipides_manual = lipides
        error.resolved_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(error)
        return error

    async def count_by_user_and_status(
        self, user_id: uuid.UUID, status: MacroErrorStatus
    ) -> int:
        result = await self._session.execute(
            select(sa_func.count(MacroError.id))
            .where(MacroError.user_id == user_id)
            .where(MacroError.status == status)
        )
        return result.scalar_one()

    @staticmethod
    def _build_slug(raw_ingredient: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S%f")
        return slugify(f"{raw_ingredient}-{ts}")