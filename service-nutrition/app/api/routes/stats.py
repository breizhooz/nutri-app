import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.models.enums.enums import MacroErrorStatus
from app.repositories.macro_error_repository import MacroErrorRepository
from app.schemas.calculate import MacroValues, UserStatsResponse

router = APIRouter()


@router.get("/users/{user_slug}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_slug: str,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> UserStatsResponse:
    """Stats nutritionnelles agrégées du user sur les 30 derniers jours."""
    try:
        user_id = uuid.UUID(user_slug)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("errors.invalid_payload"),
        )
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )

    repo = MacroErrorRepository(session)
    pending = await repo.count_by_user_and_status(user_id, MacroErrorStatus.PENDING)
    resolved = await repo.count_by_user_and_status(user_id, MacroErrorStatus.RESOLVED)
    manual = await repo.count_by_user_and_status(user_id, MacroErrorStatus.MANUAL)

    return UserStatsResponse(
        user_slug=user_slug,
        period="last_30_days",
        recipes_analysed=0,
        macro_errors_pending=pending,
        macro_errors_resolved=resolved + manual,
        avg_daily=MacroValues(calories=0, proteines=0, glucides=0, lipides=0),
    )