"""Matériel de clés E2E zero-knowledge (Phase 3) — service-user.

Stocke, par utilisateur, les éléments **opaques** calculés CÔTÉ CLIENT qui
permettent de retrouver la clé utilisateur (UK) sur n'importe quel appareil :

- ``salt`` + paramètres Argon2id (``kdf_*``) : dérivation de la Master Key (MK)
  depuis le mot de passe.
- ``wrapped_uk`` : la UK chiffrée (AES-GCM) par la MK.
- ``recovery_salt`` + ``wrapped_uk_recovery`` : la UK chiffrée par la Recovery
  Key, elle-même dérivée du code de récupération.

Le serveur ne voit JAMAIS le mot de passe, le code de récupération, la MK, la RK
ni la UK : tout est opaque. Cf. docs/rgpd/plan_dpo.md §1.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserKeyMaterial(Base):
    """Enveloppe de clés (opaque) d'un utilisateur — relation 1-1 avec ``users``."""

    __tablename__ = "user_key_material"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Dérivation de la Master Key (mêmes paramètres réutilisés pour la Recovery Key).
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kdf_memory_mib: Mapped[int] = mapped_column(Integer, nullable=False)
    kdf_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    kdf_parallelism: Mapped[int] = mapped_column(Integer, nullable=False)

    # UK chiffrée par la MK.
    wrapped_uk: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Voie de récupération : UK chiffrée par la RK (dérivée du code de récup + recovery_salt).
    recovery_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapped_uk_recovery: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
