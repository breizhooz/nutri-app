from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.unit_conversion_repository import UnitConversionRepository


class UnitConverter:
    _COMMON: dict[str, float] = {
        "g": 1.0,
        "kg": 1000.0,
        "ml": 1.0,
        "l": 1000.0,
        "cl": 10.0,
        "dl": 100.0,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UnitConversionRepository(session)

    async def to_grammes(
        self,
        quantite: float,
        unite: str,
        aliment_type: str | None = None,
    ) -> float | None:
        u = unite.lower().strip()
        if u in self._COMMON:
            return quantite * self._COMMON[u]
        conv = await self._repo.find(u, aliment_type)
        if conv:
            return quantite * conv.grammes
        return None