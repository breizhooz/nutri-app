"""Colonnes réutilisables du coffre de blobs chiffrés (E2E zero-knowledge).

Le serveur ne stocke que du **ciphertext opaque** (chiffré côté client) + une
enveloppe claire minimale servant uniquement à l'adressage : ``account_id``
(partition), ``collection`` (type de données), ``ref_key`` (clé de ressource,
ex. ``"default"`` ou une date). ``content_version`` sert au contrôle de
concurrence multi-appareils (verrouillage optimiste via ``If-Match``).

Le serveur ne voit JAMAIS le clair ni la clé. Chaque service lie ce mixin à sa
propre ``Base`` et choisit son ``__tablename__`` :

    class EncryptedBlob(Base, EncryptedBlobMixin):
        __tablename__ = "encrypted_blobs"
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class EncryptedBlobMixin:
    """Colonnes d'un blob chiffré, adressé par ``(account_id, collection, ref_key)``."""

    @declared_attr.directive
    def __table_args__(cls) -> tuple:  # noqa: N805
        return (
            UniqueConstraint(
                "account_id", "collection", "ref_key", name="uq_encrypted_blobs_addr"
            ),
        )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
