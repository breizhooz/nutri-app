from __future__ import annotations

import csv
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums.enums import NutritionSource
from app.repositories.nutrition_item_repository import NutritionItemRepository
from app.services.lookup_service import LookupService

logger = logging.getLogger(__name__)


class CiqualImporter:
    """Parse le CSV Ciqual (ANSES) et importe les NutritionItem en base."""

    _COL_ID = "alim_code"
    _COL_NOM_FR = "alim_nom_fr"
    _COL_ENERGIE = "energie_kcal"
    _COL_PROTEINES = "proteines_g"
    _COL_GLUCIDES = "glucides_g"
    _COL_LIPIDES = "lipides_g"
    _COL_FIBRES = "fibres_g"

    def __init__(
        self,
        session: AsyncSession,
        lookup: LookupService | None = None,
    ) -> None:
        self._repo = NutritionItemRepository(session)
        self._lookup = lookup or LookupService()

    async def import_csv(self, path: str | Path) -> tuple[int, int]:
        """Importe le CSV. Retourne (created, skipped)."""
        created, skipped = 0, 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            if reader.fieldnames:
                reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

            for row in reader:
                try:
                    ciqual_id = row.get(self._COL_ID, "").strip()
                    nom_fr = row.get(self._COL_NOM_FR, "").strip()

                    if not ciqual_id or not nom_fr:
                        skipped += 1
                        continue

                    if await self._repo.get_by_ciqual_id(ciqual_id):
                        skipped += 1
                        continue

                    item = await self._repo.create(
                        nom_fr=nom_fr,
                        calories=self._parse_float(row.get(self._COL_ENERGIE)),
                        proteines=self._parse_float(row.get(self._COL_PROTEINES)),
                        glucides=self._parse_float(row.get(self._COL_GLUCIDES)),
                        lipides=self._parse_float(row.get(self._COL_LIPIDES)),
                        fibres=self._parse_float(row.get(self._COL_FIBRES)) or None,
                        source=NutritionSource.CIQUAL,
                        ciqual_id=ciqual_id,
                    )
                    await self._lookup.index_item(item)
                    created += 1
                except Exception as exc:
                    logger.warning("Ciqual row skipped: %s — %s", row, exc)
                    skipped += 1

        return created, skipped

    @staticmethod
    def _parse_float(value: str | None) -> float:
        if not value:
            return 0.0
        cleaned = value.replace(",", ".").replace("<", "").strip()
        if cleaned in ("-", "", "traces"):
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0