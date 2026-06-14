"""Modèle EncryptedBlob — coffre opaque pour le chiffrement E2E zero-knowledge.

Le serveur ne stocke que du **ciphertext opaque** (chiffré côté client) + une
enveloppe claire minimale servant uniquement à l'adressage :
``account_id`` (partition), ``collection`` (type de données), ``ref_key`` (clé de
ressource, ex. ``"default"`` ou une date). ``content_version`` sert au contrôle
de concurrence multi-appareils (verrouillage optimiste via If-Match).

Le serveur ne voit JAMAIS le clair ni la clé. Cf. ../../../docs/rgpd/plan_dpo.md.
"""

import uuid

from sqlalchemy import Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.models.base_model import TimestampMixin, UpdatedAtMixin


class EncryptedBlob(Base, TimestampMixin, UpdatedAtMixin):
    """Blob chiffré côté client, adressé par (account_id, collection, ref_key)."""

    __tablename__ = "encrypted_blobs"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "collection", "ref_key", name="uq_encrypted_blobs_addr"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
