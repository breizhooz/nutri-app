"""Routes de consentement RGPD (art. 9, Phase 2).

Permettent à l'utilisateur connecté de consulter, accorder ou retirer ses
consentements (notamment ``health_data``). Le journal sous-jacent est
append-only (cf. ``ConsentService``). Le retrait du consentement santé prend
effet sur le garde-fou de service-profile au prochain rafraîchissement du token.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.consent import ConsentOut, ConsentRecordIn
from app.services.consent_service import ConsentService

router = APIRouter()


@router.get("/me/consents", response_model=list[ConsentOut])
async def list_my_consents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConsentOut]:
    """État courant des consentements de l'utilisateur (dernière trace par type)."""
    consents = await ConsentService(session).list_current(current_user.id)
    return [ConsentOut.model_validate(c) for c in consents]


@router.post("/me/consents", response_model=ConsentOut)
async def record_my_consent(
    data: ConsentRecordIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsentOut:
    """Enregistre un octroi ou un retrait de consentement (append-only)."""
    consent = await ConsentService(session).record(
        current_user.id, data.consent_type, data.version, data.granted
    )
    return ConsentOut.model_validate(consent)
