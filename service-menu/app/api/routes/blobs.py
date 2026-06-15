"""Coffre de blobs chiffrés (E2E zero-knowledge) — collection « weekly_menu ».

Le menu hebdomadaire est généré et chiffré côté client (catalogue public +
contraintes du profil dérivées localement) ; le serveur ne range que du
ciphertext opaque. Les routes minces, le verrouillage optimiste (``If-Match``)
et la sémantique 404/412 sont mutualisés dans
:func:`nutri_shared.blobs.build_blob_router`. Cf. docs/rgpd/plan_dpo.md §3.
"""

from fastapi import Depends
from nutri_shared.blobs import PgEncryptedBlobStore, build_blob_router
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_locale, get_read_account_id, get_write_account_id
from app.db.session import get_session
from app.i18n.loader import t
from app.models.encrypted_blob import EncryptedBlob


def get_blob_store(
    session: AsyncSession = Depends(get_session),
) -> PgEncryptedBlobStore:
    return PgEncryptedBlobStore(session, EncryptedBlob)


# service-menu n'expose que la collection « weekly_menu ». Pas de garde de
# consentement spécifique : le menu est une donnée fonctionnelle du compte
# (le scope plan:read / plan:write borne déjà l'accès).
router = build_blob_router(
    get_store=get_blob_store,
    get_read_account_id=get_read_account_id,
    get_write_account_id=get_write_account_id,
    get_locale=get_locale,
    translate=t.get,
    allowed_collections=frozenset({"weekly_menu"}),
)
