"""Tests du coffre de blobs chiffrés (E2E zero-knowledge).

Le fixture ``client`` injecte le compte actif + neutralise le garde consentement
(testé ailleurs). L'isolation par compte est vérifiée via ``raw_client`` + JWT forgés.
"""

import base64
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import make_context_token

# Ciphertext binaire arbitraire (le serveur ne l'interprète jamais).
_BYTES = bytes(range(256)) * 4
_B64 = base64.b64encode(_BYTES).decode()
_RW = ["profile:read", "profile:write"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestEncryptedBlobs:
    @pytest.mark.unit
    async def test_put_then_get_roundtrip(self, client: AsyncClient) -> None:
        """PUT puis GET : le ciphertext est rendu à l'identique, version 1, ETag posé."""
        put = await client.put(
            "/api/v1/profiles/me/blobs/health/default", json={"ciphertext": _B64}
        )
        assert put.status_code == 200
        assert put.json()["content_version"] == 1
        assert put.headers["ETag"] == "1"

        get = await client.get("/api/v1/profiles/me/blobs/health/default")
        assert get.status_code == 200
        body = get.json()
        assert body["ciphertext"] == _B64
        assert base64.b64decode(body["ciphertext"]) == _BYTES
        assert get.headers["ETag"] == "1"

    @pytest.mark.unit
    async def test_update_increments_version_with_if_match(self, client: AsyncClient) -> None:
        """Mise à jour avec If-Match correct → version incrémentée."""
        await client.put("/api/v1/profiles/me/blobs/health/default", json={"ciphertext": _B64})
        upd = await client.put(
            "/api/v1/profiles/me/blobs/health/default",
            json={"ciphertext": _B64},
            headers={"If-Match": "1"},
        )
        assert upd.status_code == 200
        assert upd.json()["content_version"] == 2

    @pytest.mark.unit
    async def test_stale_if_match_conflict(self, client: AsyncClient) -> None:
        """If-Match périmé → 412 ; le blob n'est pas écrasé (version inchangée)."""
        await client.put("/api/v1/profiles/me/blobs/health/default", json={"ciphertext": _B64})
        conflict = await client.put(
            "/api/v1/profiles/me/blobs/health/default",
            json={"ciphertext": _B64},
            headers={"If-Match": "99"},
        )
        assert conflict.status_code == 412
        # le client re-GET pour relire la version courante (toujours 1)
        get = await client.get("/api/v1/profiles/me/blobs/health/default")
        assert get.json()["content_version"] == 1

    @pytest.mark.unit
    async def test_if_match_on_absent_blob_conflict(self, client: AsyncClient) -> None:
        """If-Match non nul alors que le blob n'existe pas → 412."""
        resp = await client.put(
            "/api/v1/profiles/me/blobs/health/ghost",
            json={"ciphertext": _B64},
            headers={"If-Match": "3"},
        )
        assert resp.status_code == 412

    @pytest.mark.unit
    async def test_get_missing_404(self, client: AsyncClient) -> None:
        assert (
            await client.get("/api/v1/profiles/me/blobs/health/nope")
        ).status_code == 404

    @pytest.mark.unit
    async def test_delete_then_absent(self, client: AsyncClient) -> None:
        await client.put("/api/v1/profiles/me/blobs/health/default", json={"ciphertext": _B64})
        assert (
            await client.delete("/api/v1/profiles/me/blobs/health/default")
        ).status_code == 204
        assert (
            await client.get("/api/v1/profiles/me/blobs/health/default")
        ).status_code == 404
        # supprimer un blob absent → 404
        assert (
            await client.delete("/api/v1/profiles/me/blobs/health/default")
        ).status_code == 404

    @pytest.mark.unit
    async def test_list_returns_envelopes_without_ciphertext(self, client: AsyncClient) -> None:
        await client.put("/api/v1/profiles/me/blobs/health/a", json={"ciphertext": _B64})
        await client.put("/api/v1/profiles/me/blobs/health/b", json={"ciphertext": _B64})
        resp = await client.get("/api/v1/profiles/me/blobs/health")
        assert resp.status_code == 200
        items = resp.json()
        assert {i["ref_key"] for i in items} >= {"a", "b"}
        assert all("ciphertext" not in i for i in items)

    @pytest.mark.unit
    async def test_unknown_collection_404(self, client: AsyncClient) -> None:
        assert (
            await client.get("/api/v1/profiles/me/blobs/secret/default")
        ).status_code == 404
        assert (
            await client.put(
                "/api/v1/profiles/me/blobs/secret/default", json={"ciphertext": _B64}
            )
        ).status_code == 404

    @pytest.mark.unit
    async def test_invalid_base64_400(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/v1/profiles/me/blobs/health/default",
            json={"ciphertext": "!!! pas du base64 !!!"},
        )
        assert resp.status_code == 400

    @pytest.mark.unit
    async def test_account_isolation(self, raw_client: AsyncClient) -> None:
        """Un blob d'un compte n'est jamais visible par un autre compte."""
        account_a, account_b = uuid.uuid4(), uuid.uuid4()
        sub = uuid.uuid4()
        token_a = make_context_token(sub=sub, account_id=account_a, scopes=_RW)
        token_b = make_context_token(sub=sub, account_id=account_b, scopes=_RW)

        put = await raw_client.put(
            "/api/v1/profiles/me/blobs/health/default",
            json={"ciphertext": _B64},
            headers=_auth(token_a),
        )
        assert put.status_code == 200

        # compte B ne voit rien
        assert (
            await raw_client.get(
                "/api/v1/profiles/me/blobs/health/default", headers=_auth(token_b)
            )
        ).status_code == 404
        # compte A retrouve son blob
        assert (
            await raw_client.get(
                "/api/v1/profiles/me/blobs/health/default", headers=_auth(token_a)
            )
        ).status_code == 200
