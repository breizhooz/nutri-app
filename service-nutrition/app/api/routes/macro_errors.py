import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.models.enums.enums import MacroErrorStatus
from app.repositories.macro_error_repository import MacroErrorRepository
from app.schemas.macro_error import MacroErrorPatch, MacroErrorResponse

router = APIRouter()


@router.get("/users/{user_slug}/macro-errors", response_model=list[MacroErrorResponse])
async def list_macro_errors(
    user_slug: str,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[MacroErrorResponse]:
    """Liste les erreurs de résolution d'ingrédients du user."""
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
    return await MacroErrorRepository(session).get_by_user_id(user_id)


@router.patch("/macro-errors/{slug}", response_model=MacroErrorResponse)
async def patch_macro_error(
    slug: str,
    data: MacroErrorPatch,
    session: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> MacroErrorResponse:
    """Corrige un ingrédient non résolu (nom ou macros manuelles)."""
    repo = MacroErrorRepository(session)
    error = await repo.get_by_slug(slug)

    if not error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("macro_error.not_found"),
        )
    if error.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=t.get("errors.forbidden"),
        )
    if error.status != MacroErrorStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=t.get("macro_error.errors.already_resolved"),
        )

    return await repo.resolve(
        error,
        resolved_name=data.resolved_name,
        calories=data.calories_manual,
        proteines=data.proteines_manual,
        glucides=data.glucides_manual,
        lipides=data.lipides_manual,
    )