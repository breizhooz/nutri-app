"""Modèle EncryptedBlob — coffre opaque pour le chiffrement E2E zero-knowledge.

Les colonnes sont mutualisées dans :class:`nutri_shared.blobs.EncryptedBlobMixin`
(le serveur ne stocke que du ciphertext opaque + une enveloppe d'adressage). Ce
service expose la collection « weekly_menu » : le menu hebdomadaire est désormais
généré et chiffré côté client. Cf. ../../../docs/rgpd/plan_dpo.md.
"""

from nutri_shared.blobs import EncryptedBlobMixin

from app.db.base_class import Base


class EncryptedBlob(Base, EncryptedBlobMixin):
    """Blob chiffré côté client, adressé par (account_id, collection, ref_key)."""

    __tablename__ = "encrypted_blobs"
