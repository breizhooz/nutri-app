"""Point d'import centralisé pour Alembic autogenerate.

Chaque import enregistre la table correspondante dans Base.metadata. Depuis la
bascule E2E zero-knowledge (Phase 5), service-profile ne stocke plus AUCUNE
donnée de santé en clair : seule subsiste la table opaque ``encrypted_blobs``
(ciphertext chiffré côté client). Cf. docs/rgpd/plan_dpo.md.
"""

from app.db.base_class import Base  # noqa: F401
from app.models.encrypted_blob import EncryptedBlob  # noqa: F401
