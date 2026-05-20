from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class OFFProduct:
    off_id: str
    nom_fr: str
    calories: float | None
    proteines: float | None
    glucides: float | None
    lipides: float | None
    fibres: float | None


class OpenFoodFactsClient:
    _BASE_URL: str = settings.OFF_BASE_URL
    _USER_AGENT: str = settings.OFF_USER_AGENT
    _PAGE_SIZE: int = 5

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(
            base_url=self._BASE_URL,
            headers={"User-Agent": self._USER_AGENT},
            timeout=10.0,
        ) as client:
            yield client

    async def search(self, name: str) -> OFFProduct | None:
        """Cherche un aliment par nom, retourne le meilleur résultat ou None."""
        params = {
            "search_terms": name,
            "search_simple": "1",
            "action": "process",
            "json": "1",
            "fields": "product_name,nutriments,code",
            "page_size": self._PAGE_SIZE,
            "lc": "fr",
        }
        async with self._client() as client:
            try:
                resp = await client.get("/cgi/search.pl", params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                return None

        data = resp.json()
        products = data.get("products", [])
        if not products:
            return None

        return self._parse_product(products[0])

    async def get_by_barcode(self, barcode: str) -> OFFProduct | None:
        """Récupère un produit par code-barres."""
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"/api/v2/product/{barcode}",
                    params={"fields": "product_name,nutriments,code"},
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                return None

        data = resp.json()
        if data.get("status") != 1:
            return None

        return self._parse_product(data.get("product", {}))

    @staticmethod
    def _parse_product(product: dict) -> OFFProduct | None:
        code = product.get("code", "")
        nom = product.get("product_name", "").strip()
        if not nom:
            return None

        n = product.get("nutriments", {})

        def _f(key: str) -> float | None:
            val = n.get(key)
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        return OFFProduct(
            off_id=code,
            nom_fr=nom,
            calories=_f("energy-kcal_100g"),
            proteines=_f("proteins_100g"),
            glucides=_f("carbohydrates_100g"),
            lipides=_f("fat_100g"),
            fibres=_f("fiber_100g"),
        )