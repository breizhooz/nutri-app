from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.db.session import get_session
from app.i18n.loader import t
from app.repositories.nutrition_item_repository import NutritionItemRepository
from app.schemas.nutrition_item import NutritionItemResponse, NutritionItemUpdate

router = APIRouter()


@router.get("/{slug}", response_model=NutritionItemResponse)
async def get_nutrition_item(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> NutritionItemResponse:
    """Retourne le détail nutritionnel d'un aliment."""
    item = await NutritionItemRepository(session).get_by_slug(slug)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("nutrition_item.not_found"),
        )
    return item


@router.patch("/{slug}", response_model=NutritionItemResponse)
async def update_nutrition_item(
    slug: str,
    data: NutritionItemUpdate,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user_id),
) -> NutritionItemResponse:
    """Met à jour les données nutritionnelles d'un aliment (admin)."""
    repo = NutritionItemRepository(session)
    item = await repo.get_by_slug(slug)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=t.get("nutrition_item.not_found"),
        )
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return item
    return await repo.update(item, **updates)