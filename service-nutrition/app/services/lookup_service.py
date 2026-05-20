from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

_MIN_SCORE = 1.0


@dataclass
class LookupResult:
    slug: str
    nom_fr: str
    calories: float
    proteines: float
    glucides: float
    lipides: float
    fibres: float | None
    score: float


class LookupService:
    """Fuzzy match Elasticsearch sur le référentiel nutritionnel.

    Le client ES est injectable pour les tests.
    """

    def __init__(self, es_client=None) -> None:
        self._es = es_client

    def _get_client(self):
        if self._es is not None:
            return self._es
        from elasticsearch import AsyncElasticsearch
        if not hasattr(self, "_owned_client"):
            self._owned_client = AsyncElasticsearch(settings.ELASTICSEARCH_URL)
        return self._owned_client

    async def search(self, query: str, size: int = 5) -> list[LookupResult]:
        """Retourne les candidats au-dessus du seuil de score, ou liste vide."""
        client = self._get_client()
        try:
            resp = await client.search(
                index=settings.ELASTICSEARCH_INDEX,
                body={
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["nom_fr^2", "nom_en"],
                            "fuzziness": "AUTO",
                        }
                    },
                    "size": size,
                },
            )
        except Exception as exc:
            logger.error("Elasticsearch error: %s", exc)
            return []

        results = []
        for hit in resp["hits"]["hits"]:
            score = hit["_score"]
            if score < _MIN_SCORE:
                continue
            src = hit["_source"]
            results.append(
                LookupResult(
                    slug=src["slug"],
                    nom_fr=src["nom_fr"],
                    calories=src["calories"],
                    proteines=src["proteines"],
                    glucides=src["glucides"],
                    lipides=src["lipides"],
                    fibres=src.get("fibres"),
                    score=score,
                )
            )
        return results

    async def index_item(self, item) -> None:
        client = self._get_client()
        try:
            await client.index(
                index=settings.ELASTICSEARCH_INDEX,
                id=str(item.id),
                document={
                    "slug": item.slug,
                    "nom_fr": item.nom_fr,
                    "nom_en": item.nom_en,
                    "calories": item.calories,
                    "proteines": item.proteines,
                    "glucides": item.glucides,
                    "lipides": item.lipides,
                    "fibres": item.fibres,
                },
            )
        except Exception as exc:
            logger.error("ES index error (slug=%s): %s", item.slug, exc)