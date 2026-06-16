"""Tests du coffre de blobs chiffrés (E2E zero-knowledge) — collection weekly_menu.

Le serveur ne range que du ciphertext opaque, borné par le compte actif. On
vérifie le roundtrip, le verrouillage optimiste (If-Match), le listing
d'enveloppes, l'allowlist de collection et l'isolation entre comptes. Les
identifiants de compte sont de vrais UUID (la fabrique coerce ``str`` -> UUID).
"""

import base64
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import get_read_account_id, get_write_account_id
from app.db.session import get_session
from app.main import app

# Ciphertext binaire arbitraire (le serveur ne l'interprète jamais).
_BYTES = bytes(range(256)) * 4
_B64 = base64.b64encode(_BYTES).decode()

_ACCOUNT_A = str(uuid.uuid4())
_ACCOUNT_B = str(uuid.uuid4())


def _make_client(session, account_id: str) -> AsyncClient:
    async def _get_session():
        yield session

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_read_account_id] = lambda: account_id
    app.dependency_overrides[get_write_account_id] = lambda: account_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def blob_client(session) -> AsyncClient:
    async with _make_client(session, _ACCOUNT_A) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestEncryptedMenuBlobs:
    @pytest.mark.integration
    async def test_put_then_get_roundtrip(self, blob_client: AsyncClient) -> None:
        put = await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default", json={"ciphertext": _B64}
        )
        assert put.status_code == 200
        assert put.json()["content_version"] == 1
        assert put.headers["ETag"] == "1"

        get = await blob_client.get("/api/v1/menus/me/blobs/weekly_menu/default")
        assert get.status_code == 200
        body = get.json()
        assert body["ciphertext"] == _B64
        assert base64.b64decode(body["ciphertext"]) == _BYTES
        assert get.headers["ETag"] == "1"

    @pytest.mark.integration
    async def test_update_increments_version_with_if_match(
        self, blob_client: AsyncClient
    ) -> None:
        await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default", json={"ciphertext": _B64}
        )
        upd = await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default",
            json={"ciphertext": _B64},
            headers={"If-Match": "1"},
        )
        assert upd.status_code == 200
        assert upd.json()["content_version"] == 2

    @pytest.mark.integration
    async def test_stale_if_match_conflict(self, blob_client: AsyncClient) -> None:
        await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default", json={"ciphertext": _B64}
        )
        conflict = await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default",
            json={"ciphertext": _B64},
            headers={"If-Match": "99"},
        )
        assert conflict.status_code == 412
        assert conflict.headers["ETag"] == "1"
        get = await blob_client.get("/api/v1/menus/me/blobs/weekly_menu/default")
        assert get.json()["content_version"] == 1

    @pytest.mark.integration
    async def test_get_missing_404(self, blob_client: AsyncClient) -> None:
        resp = await blob_client.get("/api/v1/menus/me/blobs/weekly_menu/nope")
        assert resp.status_code == 404

    @pytest.mark.integration
    async def test_delete_then_absent(self, blob_client: AsyncClient) -> None:
        await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default", json={"ciphertext": _B64}
        )
        assert (
            await blob_client.delete("/api/v1/menus/me/blobs/weekly_menu/default")
        ).status_code == 204
        assert (
            await blob_client.get("/api/v1/menus/me/blobs/weekly_menu/default")
        ).status_code == 404
        assert (
            await blob_client.delete("/api/v1/menus/me/blobs/weekly_menu/default")
        ).status_code == 404

    @pytest.mark.integration
    async def test_list_returns_envelopes_without_ciphertext(
        self, blob_client: AsyncClient
    ) -> None:
        await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/a", json={"ciphertext": _B64}
        )
        await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/b", json={"ciphertext": _B64}
        )
        resp = await blob_client.get("/api/v1/menus/me/blobs/weekly_menu")
        assert resp.status_code == 200
        items = resp.json()
        assert {i["ref_key"] for i in items} >= {"a", "b"}
        assert all("ciphertext" not in i for i in items)

    @pytest.mark.integration
    async def test_unknown_collection_404(self, blob_client: AsyncClient) -> None:
        # service-menu n'expose que weekly_menu ; « health » lui est inconnue.
        assert (
            await blob_client.get("/api/v1/menus/me/blobs/health/default")
        ).status_code == 404
        assert (
            await blob_client.put(
                "/api/v1/menus/me/blobs/health/default", json={"ciphertext": _B64}
            )
        ).status_code == 404

    @pytest.mark.integration
    async def test_invalid_base64_400(self, blob_client: AsyncClient) -> None:
        resp = await blob_client.put(
            "/api/v1/menus/me/blobs/weekly_menu/default",
            json={"ciphertext": "!!! pas du base64 !!!"},
        )
        assert resp.status_code == 400

    @pytest.mark.integration
    async def test_account_isolation(self, session) -> None:
        """Un blob d'un compte n'est jamais visible par un autre compte."""
        async with _make_client(session, _ACCOUNT_A) as client_a:
            put = await client_a.put(
                "/api/v1/menus/me/blobs/weekly_menu/default", json={"ciphertext": _B64}
            )
            assert put.status_code == 200

        async with _make_client(session, _ACCOUNT_B) as client_b:
            assert (
                await client_b.get("/api/v1/menus/me/blobs/weekly_menu/default")
            ).status_code == 404

        async with _make_client(session, _ACCOUNT_A) as client_a:
            assert (
                await client_a.get("/api/v1/menus/me/blobs/weekly_menu/default")
            ).status_code == 200

        app.dependency_overrides.clear()
