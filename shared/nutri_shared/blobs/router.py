"""Fabrique de routes minces pour le coffre de blobs chiffrés (E2E zero-knowledge).

Le serveur ne fait que ranger/rendre des octets opaques, bornés par le compte
actif. Aucune logique métier ici. Concurrence multi-appareils gérée par
``content_version`` + en-tête ``If-Match`` (verrouillage optimiste). Cf.
docs/rgpd/plan_dpo.md §3.

Chaque service appelle :func:`build_blob_router` en injectant ses propres
dépendances (résolution du compte actif, locale, traduction, garde de
consentement éventuelle) et la liste de collections qu'il expose. Les routes,
le parsing ``If-Match``, le décodage base64 et la sémantique 404/412 sont
mutualisés.
"""

import base64
import binascii
import uuid
from collections.abc import Callable, Sequence

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Request,
    Response,
    status,
)

from nutri_shared.blobs.schemas import BlobEnvelopeOut, BlobOut, BlobPutIn
from nutri_shared.blobs.store import BlobConflictError, EncryptedBlobStore

_REF_KEY_PATTERN = r"^[A-Za-z0-9._-]{1,128}$"


def _as_uuid(value: object) -> uuid.UUID:
    """Coerce l'identifiant de compte (str ou UUID selon le service) en UUID."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def build_blob_router(
    *,
    get_store: Callable[..., EncryptedBlobStore],
    get_read_account_id: Callable[..., object],
    get_write_account_id: Callable[..., object],
    get_locale: Callable[[Request], str],
    translate: Callable[..., str],
    allowed_collections: frozenset[str],
    write_dependencies: Sequence[Callable[..., object]] = (),
) -> APIRouter:
    """Construit un routeur ``/me/blobs/...`` paramétré par le service.

    - ``get_store`` : dépendance fournissant un :class:`EncryptedBlobStore`.
    - ``get_read_account_id`` / ``get_write_account_id`` : dépendances bornant le
      périmètre au compte actif (peuvent renvoyer ``str`` ou ``uuid.UUID``).
    - ``translate`` : ``(clé_i18n, locale) -> message`` (typiquement ``loader.get``).
    - ``allowed_collections`` : collections exposées par ce service.
    - ``write_dependencies`` : gardes supplémentaires sur les écritures
      (ex. ``require_health_consent`` pour la collection santé).
    """
    router = APIRouter()
    write_guards = [Depends(dep) for dep in write_dependencies]

    def _ensure_collection(request: Request, collection: str) -> None:
        if collection not in allowed_collections:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("errors.blob_collection_unknown", get_locale(request)),
            )

    def _parse_if_match(if_match: str | None) -> int | None:
        """Parse l'en-tête If-Match (ETag faible/fort, guillemets) en entier de version."""
        if if_match is None:
            return None
        cleaned = if_match.strip().removeprefix("W/").strip().strip('"')
        try:
            return int(cleaned)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="If-Match invalide"
            )

    def _decode_ciphertext(request: Request, b64: str) -> bytes:
        try:
            return base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate("errors.blob_ciphertext_invalid", get_locale(request)),
            )

    @router.get("/me/blobs/{collection}", response_model=list[BlobEnvelopeOut])
    async def list_blobs(
        request: Request,
        collection: str = Path(..., max_length=64),
        account_id: object = Depends(get_read_account_id),
        store: EncryptedBlobStore = Depends(get_store),
    ) -> list[BlobEnvelopeOut]:
        """Liste les enveloppes (sans ciphertext) d'une collection — synchro multi-appareils."""
        _ensure_collection(request, collection)
        envelopes = await store.list(_as_uuid(account_id), collection)
        return [BlobEnvelopeOut(**vars(e)) for e in envelopes]

    @router.get("/me/blobs/{collection}/{ref_key}", response_model=BlobOut)
    async def get_blob(
        request: Request,
        response: Response,
        collection: str = Path(..., max_length=64),
        ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
        account_id: object = Depends(get_read_account_id),
        store: EncryptedBlobStore = Depends(get_store),
    ) -> BlobOut:
        """Récupère un blob chiffré. 404 s'il n'existe pas."""
        _ensure_collection(request, collection)
        record = await store.get(_as_uuid(account_id), collection, ref_key)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("errors.blob_not_found", get_locale(request)),
            )
        response.headers["ETag"] = str(record.content_version)
        return BlobOut(
            collection=record.collection,
            ref_key=record.ref_key,
            content_version=record.content_version,
            ciphertext=base64.b64encode(record.ciphertext).decode(),
        )

    @router.put(
        "/me/blobs/{collection}/{ref_key}",
        response_model=BlobOut,
        dependencies=write_guards,
    )
    async def put_blob(
        request: Request,
        response: Response,
        data: BlobPutIn,
        collection: str = Path(..., max_length=64),
        ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
        if_match: str | None = Header(default=None, alias="If-Match"),
        account_id: object = Depends(get_write_account_id),
        store: EncryptedBlobStore = Depends(get_store),
    ) -> BlobOut:
        """Crée ou met à jour un blob. ``If-Match: <content_version>`` pour la concurrence."""
        _ensure_collection(request, collection)
        ciphertext = _decode_ciphertext(request, data.ciphertext)
        expected = _parse_if_match(if_match)
        try:
            record = await store.put(
                _as_uuid(account_id), collection, ref_key, ciphertext, expected
            )
        except BlobConflictError as exc:
            # ETag = version courante → le client peut fusionner sans re-GET.
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=translate("errors.blob_version_conflict", get_locale(request)),
                headers={"ETag": str(exc.current_version)},
            )
        response.headers["ETag"] = str(record.content_version)
        return BlobOut(
            collection=record.collection,
            ref_key=record.ref_key,
            content_version=record.content_version,
            ciphertext=base64.b64encode(record.ciphertext).decode(),
        )

    @router.delete(
        "/me/blobs/{collection}/{ref_key}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=write_guards,
    )
    async def delete_blob(
        request: Request,
        collection: str = Path(..., max_length=64),
        ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
        account_id: object = Depends(get_write_account_id),
        store: EncryptedBlobStore = Depends(get_store),
    ) -> None:
        """Supprime un blob. 404 s'il n'existe pas."""
        _ensure_collection(request, collection)
        if not await store.delete(_as_uuid(account_id), collection, ref_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=translate("errors.blob_not_found", get_locale(request)),
            )

    return router
