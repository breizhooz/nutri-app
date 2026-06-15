"""Coffre de blobs chiffrés (E2E zero-knowledge) — collection « health ».

Les routes minces, le verrouillage optimiste (``If-Match``) et la sémantique
404/412 sont mutualisés dans :func:`nutri_shared.blobs.build_blob_router`. Ce
service ne fait qu'injecter ses dépendances (scope du compte actif, locale, i18n)
et garde les écritures derrière le consentement santé (RGPD art. 9).
Cf. docs/rgpd/plan_dpo.md §3.
"""

from nutri_shared.blobs import PgEncryptedBlobStore, build_blob_router
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.deps import (
    get_locale,
    get_read_account_id,
    get_write_account_id,
    require_health_consent,
)
from app.db.session import get_session
from app.i18n.loader import t
from app.models.encrypted_blob import EncryptedBlob


def get_blob_store(
    session: AsyncSession = Depends(get_session),
) -> PgEncryptedBlobStore:
    return PgEncryptedBlobStore(session, EncryptedBlob)


# service-profile n'expose que la collection « health » (donnée art. 9 RGPD :
# écritures gardées par require_health_consent).
router = build_blob_router(
    get_store=get_blob_store,
    get_read_account_id=get_read_account_id,
    get_write_account_id=get_write_account_id,
    get_locale=get_locale,
    translate=t.get,
    allowed_collections=frozenset({"health"}),
    write_dependencies=[require_health_consent],
)
