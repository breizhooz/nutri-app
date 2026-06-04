"""Tests du garde anti-SSRF (SEC-03)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.ssrf import UnsafeUrlError, assert_public_url
from app.services.web_service import WebService


# Résolveur factice : mappe un hostname vers une IP imposée (pas de DNS réseau).
def _resolver(mapping):
    return lambda host: [mapping[host]]


class TestAssertPublicUrl:
    def test_allows_public_host(self):
        assert_public_url(
            "https://example.com/recipe", resolver=_resolver({"example.com": "93.184.216.34"})
        )  # ne lève pas

    def test_allows_public_literal_ip(self):
        assert_public_url("http://93.184.216.34/page")  # IP publique littérale

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://localhost/",  # résout en loopback
            "http://169.254.169.254/latest/meta-data/",  # métadonnées cloud
            "http://10.0.0.5/",
            "http://192.168.1.10/",
            "http://172.16.0.1/",
            "http://[::1]/",
        ],
    )
    def test_blocks_internal_literal_targets(self, url):
        # localhost a besoin d'une résolution ; les IP littérales non.
        resolver = _resolver({"localhost": "127.0.0.1"})
        with pytest.raises(UnsafeUrlError):
            assert_public_url(url, resolver=resolver)

    def test_blocks_hostname_resolving_to_private_ip(self):
        # DNS-rebinding "statique" : un domaine public qui pointe en interne.
        resolver = _resolver({"sneaky.example.com": "10.1.2.3"})
        with pytest.raises(UnsafeUrlError):
            assert_public_url("https://sneaky.example.com/", resolver=resolver)

    def test_blocks_internal_service_name(self):
        # Nom de service Docker → résout vers une IP privée.
        resolver = _resolver({"postgres": "172.18.0.2"})
        with pytest.raises(UnsafeUrlError):
            assert_public_url("http://postgres:5432/", resolver=resolver)

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "ftp://x/", "//x"])
    def test_blocks_disallowed_schemes(self, url):
        with pytest.raises(UnsafeUrlError):
            assert_public_url(url)

    def test_blocks_unresolvable_host(self):
        import socket

        def _boom(host):
            raise socket.gaierror("nope")

        with pytest.raises(UnsafeUrlError):
            assert_public_url("https://does-not-exist.invalid/", resolver=_boom)


class TestFetchEnforcesGuard:
    @pytest.mark.asyncio
    async def test_fetch_rejects_internal_url_without_any_request(self):
        # Le garde doit bloquer AVANT toute requête httpx et SANS repli Playwright.
        with patch("app.services.web_service.httpx.AsyncClient") as mock_cls, patch.object(
            WebService, "_fetch_with_playwright", new_callable=AsyncMock
        ) as mock_pw:
            with pytest.raises(UnsafeUrlError):
                await WebService().fetch("http://169.254.169.254/latest/meta-data/")

        mock_cls.assert_not_called()
        mock_pw.assert_not_called()
