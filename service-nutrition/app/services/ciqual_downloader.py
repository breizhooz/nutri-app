from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import py7zr

from app.core.config import settings


class CiqualDownloader:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._injected_client = http_client

    @asynccontextmanager
    async def _client(self):
        if self._injected_client is not None:
            yield self._injected_client
            return
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            yield client

    async def download(self) -> tuple[str, str, str]:
        """
        Télécharge l'archive .7z Ciqual.
        Retourne (extract_dir, sha256, filename).
        """
        url = settings.CIQUAL_DOWNLOAD_URL
        filename = url.split("/")[-1]

        extract_dir = tempfile.mkdtemp(prefix="ciqual_")
        archive_path = os.path.join(extract_dir, filename)
        hasher = hashlib.sha256()

        async with self._client() as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(archive_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        hasher.update(chunk)

        sha256 = hasher.hexdigest()

        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            z.extractall(path=extract_dir)

        os.remove(archive_path)
        return extract_dir, sha256, filename