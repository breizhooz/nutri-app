import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_read_account_id
from app.db.session import get_session
from app.models.enums.enums import MacroErrorStatus
from app.repositories.macro_error_repository import MacroErrorRepository
from app.schemas.calculate import MacroValues, UserStatsResponse

router = APIRouter()


@router.get("/users/{user_slug}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_slug: str,
    session: AsyncSession = Depends(get_session),
    account_id: uuid.UUID = Depends(get_read_account_id),
) -> UserStatsResponse:
    """Stats nutritionnelles agrégées du compte actif sur 30 jours.

    Multicomptes : bornées par account_id (user_slug conservé pour compat d'API).
    """
    repo = MacroErrorRepository(session)
    pending = await repo.count_by_account_and_status(
        account_id, MacroErrorStatus.PENDING
    )
    resolved = await repo.count_by_account_and_status(
        account_id, MacroErrorStatus.RESOLVED
    )
    manual = await repo.count_by_account_and_status(account_id, MacroErrorStatus.MANUAL)

    return UserStatsResponse(
        user_slug=user_slug,
        period="last_30_days",
        recipes_analysed=0,
        macro_errors_pending=pending,
        macro_errors_resolved=resolved + manual,
        avg_daily=MacroValues(calories=0, proteines=0, glucides=0, lipides=0),
    )
