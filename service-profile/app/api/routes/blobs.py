"""Routes minces du coffre de blobs chiffrés (E2E zero-knowledge).

Le serveur ne fait que ranger/rendre des octets opaques, bornés par le compte
actif. Aucune logique métier santé ici. Concurrence multi-appareils gérée par
``content_version`` + en-tête ``If-Match`` (verrouillage optimiste). Cf.
docs/rgpd/plan_dpo.md §3.
"""

import base64
import binascii
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.blobs.store import BlobConflictError, EncryptedBlobStore, PgEncryptedBlobStore
from app.core.deps import (
    get_locale,
    get_read_account_id,
    get_write_account_id,
    require_health_consent,
)
from app.db.session import get_session
from app.i18n.loader import t
from app.schemas.blob import BlobEnvelopeOut, BlobOut, BlobPutIn

router = APIRouter()

# service-profile ne gère que la collection « health ». D'autres services
# exposeront leurs propres collections (ex. service-menu → « weekly_menu »).
ALLOWED_COLLECTIONS = frozenset({"health"})

_REF_KEY_PATTERN = r"^[A-Za-z0-9._-]{1,128}$"


def get_blob_store(session: AsyncSession = Depends(get_session)) -> EncryptedBlobStore:
    return PgEncryptedBlobStore(session)


def _ensure_collection(request: Request, collection: str) -> None:
    if collection not in ALLOWED_COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("errors.blob_collection_unknown", get_locale(request)),
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
            detail=t.get("errors.blob_ciphertext_invalid", get_locale(request)),
        )


@router.get("/me/blobs/{collection}", response_model=list[BlobEnvelopeOut])
async def list_blobs(
    request: Request,
    collection: str = Path(..., max_length=64),
    account_id: uuid.UUID = Depends(get_read_account_id),
    store: EncryptedBlobStore = Depends(get_blob_store),
) -> list[BlobEnvelopeOut]:
    """Liste les enveloppes (sans ciphertext) d'une collection — synchro multi-appareils."""
    _ensure_collection(request, collection)
    envelopes = await store.list(account_id, collection)
    return [BlobEnvelopeOut(**vars(e)) for e in envelopes]


@router.get("/me/blobs/{collection}/{ref_key}", response_model=BlobOut)
async def get_blob(
    request: Request,
    response: Response,
    collection: str = Path(..., max_length=64),
    ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
    account_id: uuid.UUID = Depends(get_read_account_id),
    store: EncryptedBlobStore = Depends(get_blob_store),
) -> BlobOut:
    """Récupère un blob chiffré. 404 s'il n'existe pas."""
    _ensure_collection(request, collection)
    record = await store.get(account_id, collection, ref_key)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("errors.blob_not_found", get_locale(request)),
        )
    response.headers["ETag"] = str(record.content_version)
    return BlobOut(
        collection=record.collection,
        ref_key=record.ref_key,
        content_version=record.content_version,
        ciphertext=base64.b64encode(record.ciphertext).decode(),
    )


@router.put("/me/blobs/{collection}/{ref_key}", response_model=BlobOut)
async def put_blob(
    request: Request,
    response: Response,
    data: BlobPutIn,
    collection: str = Path(..., max_length=64),
    ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
    if_match: str | None = Header(default=None, alias="If-Match"),
    account_id: uuid.UUID = Depends(get_write_account_id),
    _consent: None = Depends(require_health_consent),  # RGPD art. 9 (collection santé)
    store: EncryptedBlobStore = Depends(get_blob_store),
) -> BlobOut:
    """Crée ou met à jour un blob. ``If-Match: <content_version>`` pour la concurrence."""
    _ensure_collection(request, collection)
    ciphertext = _decode_ciphertext(request, data.ciphertext)
    expected = _parse_if_match(if_match)
    try:
        record = await store.put(account_id, collection, ref_key, ciphertext, expected)
    except BlobConflictError as exc:
        # NB : le handler d'erreur partagé (nutri_shared) ne propage pas les
        # en-têtes d'HTTPException → pas de ETag fiable sur le 412. Le client
        # re-GET la ressource pour relire content_version et fusionner. `exc`
        # porte la version courante si on enrichit le handler plus tard.
        _ = exc.current_version
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=t.get("errors.blob_version_conflict", get_locale(request)),
        )
    response.headers["ETag"] = str(record.content_version)
    return BlobOut(
        collection=record.collection,
        ref_key=record.ref_key,
        content_version=record.content_version,
        ciphertext=base64.b64encode(record.ciphertext).decode(),
    )


@router.delete(
    "/me/blobs/{collection}/{ref_key}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_blob(
    request: Request,
    collection: str = Path(..., max_length=64),
    ref_key: str = Path(..., pattern=_REF_KEY_PATTERN),
    account_id: uuid.UUID = Depends(get_write_account_id),
    _consent: None = Depends(require_health_consent),
    store: EncryptedBlobStore = Depends(get_blob_store),
) -> None:
    """Supprime un blob. 404 s'il n'existe pas."""
    _ensure_collection(request, collection)
    if not await store.delete(account_id, collection, ref_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("errors.blob_not_found", get_locale(request)),
        )
