from __future__ import annotations

import io
import os
import zipfile
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings


class CiqualDownloader:
    _DOWNLOAD_URL: str = settings.CIQUAL_DOWNLOAD_URL
    _CACHE_PATH: str = settings.CIQUAL_CACHE_PATH

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            yield client

    async def download(self) -> str:
        """
        Télécharge le ZIP Ciqual depuis l'ANSES, extrait le premier CSV trouvé,
        le sauvegarde à CIQUAL_CACHE_PATH et retourne ce chemin.
        """
        async with self._client() as client:
            resp = await client.get(self._DOWNLOAD_URL)
            resp.raise_for_status()

        csv_content = self._extract_csv(resp.content)
        self._write(csv_content)
        return self._CACHE_PATH

    @staticmethod
    def _extract_csv(zip_bytes: bytes) -> bytes:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError("Aucun fichier CSV trouvé dans le ZIP Ciqual")
            return zf.read(csv_names[0])

    def _write(self, content: bytes) -> None:
        os.makedirs(os.path.dirname(self._CACHE_PATH) or ".", exist_ok=True)
        with open(self._CACHE_PATH, "wb") as f:
            f.write(content)