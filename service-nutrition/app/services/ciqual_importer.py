from __future__ import annotations

import logging
import shutil
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ciqual_archive import CiqualArchive
from app.models.nutrition_item import NutritionItem, NutritionSource
from app.services.ciqual_xml_parser import CiqualXmlParser


logger = logging.getLogger(__name__)


class CiqualImporter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def already_imported(self, sha256: str) -> bool:
        result = await self._session.execute(
            select(CiqualArchive).where(CiqualArchive.sha256 == sha256)
        )
        return result.scalar_one_or_none() is not None

    async def import_archive(
        self, extract_dir: str, sha256: str, filename: str
    ) -> int:
        try:
            aliments = CiqualXmlParser.parse_aliments(extract_dir)
            macros = CiqualXmlParser.parse_compo(extract_dir)

            count = 0
            for alim_code, alim in aliments.items():
                nutriments = macros.get(alim_code, {})
                existing = await self._session.execute(
                    select(NutritionItem).where(NutritionItem.ciqual_id == alim_code)
                )
                item = existing.scalar_one_or_none()
                if item is None:
                    item = NutritionItem(
                        id=uuid.uuid4(),
                        ciqual_id=alim_code,
                        source=NutritionSource.ciqual,
                    )
                    self._session.add(item)

                item.nom_fr = alim.nom_fr
                item.nom_en = alim.nom_eng
                item.nom_sci = alim.nom_sci
                item.alim_grp_code = alim.alim_grp_code
                item.alim_ssgrp_code = alim.alim_ssgrp_code
                item.alim_ssssgrp_code = alim.alim_ssssgrp_code
                item.slug = _slugify(alim.nom_fr, alim_code)
                item.calories = nutriments.get("calories")
                item.proteines = nutriments.get("proteines")
                item.glucides = nutriments.get("glucides")
                item.lipides = nutriments.get("lipides")
                item.fibres = nutriments.get("fibres")
                item.code_confiance = nutriments.get("code_confiance")
                count += 1

            version = filename.replace(".7z", "")
            self._session.add(CiqualArchive(
                sha256=sha256,
                filename=filename,
                version=version,
                item_count=count,
            ))
            await self._session.commit()
            logger.info("Import Ciqual terminé : %d items", count)
            return count
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)


def _slugify(nom_fr: str, alim_code: int) -> str:
    import re
    slug = nom_fr.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return f"{slug}-{alim_code}"