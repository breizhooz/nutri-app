"""Journal de consentement RGPD (art. 9 — données de santé) — service-user.

Table **append-only et versionnée** : chaque octroi ou retrait crée une nouvelle
ligne. Le consentement « actif » pour un type donné est la ligne la plus récente
(``created_at``) de l'utilisateur ; il est effectif si ``granted`` vaut ``True``.
Conserver l'historique complet est une exigence de preuve (qui a consenti à quoi,
quand, à quelle version de la politique).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Types de consentement gérés. ``health_data`` couvre le traitement des données
# de santé (art. 9), garde-fou des écritures côté service-profile.
CONSENT_HEALTH_DATA = "health_data"
# Version courante de la politique de consentement santé (référence côté API).
HEALTH_DATA_CURRENT_VERSION = "v1"


class Consent(Base):
    """Trace immuable d'un octroi/retrait de consentement par un utilisateur."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # Type de traitement consenti (ex. ``health_data``).
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Version de la politique à laquelle l'utilisateur a consenti.
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    # True = octroi, False = retrait.
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Défaut côté Python (précision microseconde) pour départager l'ordre des
    # traces : ``func.now()`` (PG) renvoie l'heure de transaction, identique pour
    # deux lignes d'une même transaction, ce qui rendrait « la plus récente »
    # ambiguë. server_default conservé pour les insertions SQL brutes.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
