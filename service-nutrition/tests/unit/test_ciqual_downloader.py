"""Tests unitaires pour CiqualDownloader."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ciqual_downloader import CiqualDownloader


class TestCiqualDownloaderInjectedClient:
    """Teste CiqualDownloader avec un client httpx injecté (pas de réseau)."""

    def _make_client(self, content: bytes = b"fake-archive-data") -> AsyncMock:
        """Crée un faux client httpx.AsyncClient."""
        chunk = content
        response = AsyncMock()
        response.raise_for_status = MagicMock()
        response.aiter_bytes = MagicMock(return_value=_async_iter([chunk]))
        stream_ctx = AsyncMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)
        client = AsyncMock()
        client.stream = MagicMock(return_value=stream_ctx)
        return client

    @pytest.mark.unit
    async def test_download_returns_tuple(self, tmp_path):
        """download() retourne (extract_dir, sha256, filename)."""
        fake_content = b"PK\x03\x04fake-zip-content"
        client = self._make_client(fake_content)

        with (
            patch("app.services.ciqual_downloader.settings") as mock_settings,
            patch("app.services.ciqual_downloader.py7zr.SevenZipFile") as mock_7z,
            patch("app.services.ciqual_downloader.tempfile.mkdtemp") as mock_tmp,
            patch("app.services.ciqual_downloader.os.remove"),
        ):
            mock_settings.CIQUAL_DOWNLOAD_URL = (
                "http://test.example.com/ciqual_2024_01_01.7z"
            )
            mock_tmp.return_value = str(tmp_path)
            mock_7z_instance = MagicMock()
            mock_7z.return_value.__enter__ = MagicMock(return_value=mock_7z_instance)
            mock_7z.return_value.__exit__ = MagicMock(return_value=False)

            downloader = CiqualDownloader(http_client=client)
            extract_dir, sha256, filename = await downloader.download()

        assert extract_dir == str(tmp_path)
        assert len(sha256) == 64
        assert filename == "ciqual_2024_01_01.7z"

    @pytest.mark.unit
    async def test_download_sha256_matches_content(self, tmp_path):
        """Le sha256 retourné correspond au hash du contenu reçu."""
        import hashlib

        content = b"deterministic-content"
        expected_sha = hashlib.sha256(content).hexdigest()

        client = self._make_client(content)

        with (
            patch("app.services.ciqual_downloader.settings") as mock_settings,
            patch("app.services.ciqual_downloader.py7zr.SevenZipFile") as mock_7z,
            patch("app.services.ciqual_downloader.tempfile.mkdtemp") as mock_tmp,
            patch("app.services.ciqual_downloader.os.remove"),
        ):
            mock_settings.CIQUAL_DOWNLOAD_URL = "http://test.example.com/data.7z"
            mock_tmp.return_value = str(tmp_path)
            mock_7z.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_7z.return_value.__exit__ = MagicMock(return_value=False)

            downloader = CiqualDownloader(http_client=client)
            _, sha256, _ = await downloader.download()

        assert sha256 == expected_sha

    @pytest.mark.unit
    async def test_download_extracts_archive(self, tmp_path):
        """py7zr.SevenZipFile.extractall est appelé avec le bon répertoire."""
        client = self._make_client()

        with (
            patch("app.services.ciqual_downloader.settings") as mock_settings,
            patch("app.services.ciqual_downloader.py7zr.SevenZipFile") as mock_7z,
            patch("app.services.ciqual_downloader.tempfile.mkdtemp") as mock_tmp,
            patch("app.services.ciqual_downloader.os.remove"),
        ):
            mock_settings.CIQUAL_DOWNLOAD_URL = "http://test.example.com/data.7z"
            mock_tmp.return_value = str(tmp_path)
            extractor = MagicMock()
            mock_7z.return_value.__enter__ = MagicMock(return_value=extractor)
            mock_7z.return_value.__exit__ = MagicMock(return_value=False)

            downloader = CiqualDownloader(http_client=client)
            await downloader.download()

        extractor.extractall.assert_called_once_with(path=str(tmp_path))

    @pytest.mark.unit
    async def test_download_removes_archive_file(self, tmp_path):
        """L'archive .7z est supprimée après extraction."""
        client = self._make_client()

        with (
            patch("app.services.ciqual_downloader.settings") as mock_settings,
            patch("app.services.ciqual_downloader.py7zr.SevenZipFile") as mock_7z,
            patch("app.services.ciqual_downloader.tempfile.mkdtemp") as mock_tmp,
            patch("app.services.ciqual_downloader.os.remove") as mock_remove,
        ):
            mock_settings.CIQUAL_DOWNLOAD_URL = "http://test.example.com/ciqual_data.7z"
            mock_tmp.return_value = str(tmp_path)
            mock_7z.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_7z.return_value.__exit__ = MagicMock(return_value=False)

            downloader = CiqualDownloader(http_client=client)
            await downloader.download()

        expected_path = os.path.join(str(tmp_path), "ciqual_data.7z")
        mock_remove.assert_called_once_with(expected_path)

    @pytest.mark.unit
    async def test_download_raises_on_http_error(self, tmp_path):
        """Une erreur HTTP est propagée par raise_for_status."""
        import httpx

        response = AsyncMock()
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
        )
        response.aiter_bytes = MagicMock(return_value=_async_iter([]))
        stream_ctx = AsyncMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=response)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)
        client = AsyncMock()
        client.stream = MagicMock(return_value=stream_ctx)

        with (
            patch("app.services.ciqual_downloader.settings") as mock_settings,
            patch("app.services.ciqual_downloader.tempfile.mkdtemp") as mock_tmp,
        ):
            mock_settings.CIQUAL_DOWNLOAD_URL = "http://test.example.com/data.7z"
            mock_tmp.return_value = str(tmp_path)

            downloader = CiqualDownloader(http_client=client)
            with pytest.raises(httpx.HTTPStatusError):
                await downloader.download()


async def _async_iter(items):
    for item in items:
        yield item
