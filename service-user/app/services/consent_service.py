"""Logique de consentement RGPD (art. 9, Phase 2) — service-user.

Le journal ``consents`` est append-only : ``record`` insère une nouvelle ligne à
chaque octroi/retrait. L'état courant d'un type est la ligne la plus récente ;
le consentement est « actif » si cette dernière ligne a ``granted=True``.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import CONSENT_HEALTH_DATA, Consent


class ConsentService:
    """Lecture/écriture du journal de consentement d'un utilisateur."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        user_id: uuid.UUID,
        consent_type: str,
        version: str,
        granted: bool,
    ) -> Consent:
        """Ajoute une trace de consentement (octroi ou retrait). Append-only."""
        consent = Consent(
            user_id=user_id,
            consent_type=consent_type,
            version=version,
            granted=granted,
        )
        self.session.add(consent)
        await self.session.commit()
        await self.session.refresh(consent)
        return consent

    async def list_current(self, user_id: uuid.UUID) -> list[Consent]:
        """Retourne la dernière trace par type de consentement (état courant)."""
        rows = await self.session.execute(
            select(Consent)
            .where(Consent.user_id == user_id)
            .order_by(Consent.consent_type, Consent.created_at.desc())
        )
        latest: dict[str, Consent] = {}
        for consent in rows.scalars():
            latest.setdefault(consent.consent_type, consent)
        return list(latest.values())

    async def get_latest(self, user_id: uuid.UUID, consent_type: str) -> Consent | None:
        """Dernière trace pour un type donné, ou ``None`` si jamais renseigné."""
        row = await self.session.execute(
            select(Consent)
            .where(Consent.user_id == user_id, Consent.consent_type == consent_type)
            .order_by(Consent.created_at.desc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def is_active(self, user_id: uuid.UUID, consent_type: str) -> bool:
        """Indique si le consentement le plus récent est un octroi (``granted``)."""
        latest = await self.get_latest(user_id, consent_type)
        return bool(latest and latest.granted)

    async def has_active_health_consent(self, user_id: uuid.UUID) -> bool:
        """Raccourci : consentement santé (art. 9) actif ? Sert au claim JWT."""
        return await self.is_active(user_id, CONSENT_HEALTH_DATA)
