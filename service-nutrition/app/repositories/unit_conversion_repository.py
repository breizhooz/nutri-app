from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit_conversion import UnitConversion


class UnitConversionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(
        self, unite: str, aliment_type: str | None = None
    ) -> UnitConversion | None:
        """Cherche d'abord la conversion spécifique à l'aliment, puis universelle."""
        if aliment_type:
            result = await self._session.execute(
                select(UnitConversion).where(
                    UnitConversion.unite == unite,
                    UnitConversion.aliment_type == aliment_type,
                )
            )
            specific = result.scalar_one_or_none()
            if specific:
                return specific

        result = await self._session.execute(
            select(UnitConversion).where(
                UnitConversion.unite == unite,
                UnitConversion.aliment_type.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        unite: str,
        grammes: float,
        aliment_type: str | None = None,
        note: str | None = None,
    ) -> UnitConversion:
        slug = slugify(f"{unite}-{aliment_type or 'universel'}")
        conv = UnitConversion(
            slug=slug,
            unite=unite,
            aliment_type=aliment_type,
            grammes=grammes,
            note=note,
        )
        self._session.add(conv)
        await self._session.commit()
        await self._session.refresh(conv)
        return conv