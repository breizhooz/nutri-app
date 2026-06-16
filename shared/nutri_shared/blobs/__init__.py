"""Coffre de blobs chiffrés opaques (E2E zero-knowledge), mutualisé entre services.

Le serveur ne voit que du ciphertext opaque ; tout chiffrement/déchiffrement est
côté client. Chaque service lie :class:`EncryptedBlobMixin` à sa ``Base`` et monte
un routeur produit par :func:`build_blob_router`. Cf. docs/rgpd/plan_dpo.md §3.
"""

from nutri_shared.blobs.models import EncryptedBlobMixin
from nutri_shared.blobs.router import build_blob_router
from nutri_shared.blobs.schemas import BlobEnvelopeOut, BlobOut, BlobPutIn
from nutri_shared.blobs.store import (
    BlobConflictError,
    BlobEnvelope,
    BlobRecord,
    EncryptedBlobStore,
    PgEncryptedBlobStore,
)

__all__ = [
    "EncryptedBlobMixin",
    "build_blob_router",
    "BlobEnvelopeOut",
    "BlobOut",
    "BlobPutIn",
    "BlobConflictError",
    "BlobEnvelope",
    "BlobRecord",
    "EncryptedBlobStore",
    "PgEncryptedBlobStore",
]
