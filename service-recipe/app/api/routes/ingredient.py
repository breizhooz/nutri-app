from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.core.deps import get_current_user_id
from app.repositories.ingredient_repository import IngredientRepository
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientUpdate,
    IngredientResponse,
)
from app.services.ingredient_service import IngredientService

router = APIRouter(prefix="", tags=["ingredients"])


class IngredientServiceFactory:
    @staticmethod
    def inject(session: AsyncSession = Depends(get_session)) -> IngredientService:
        return IngredientService(IngredientRepository(session))


@router.post(
    "/",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user_id)],
)
async def create_ingredient(
    obj_in: IngredientCreate,
    service: IngredientService = Depends(IngredientServiceFactory.inject),
) -> IngredientResponse:
    return await service.create(obj_in)


@router.get("/", response_model=List[IngredientResponse])
async def read_ingredients(
    skip: int = 0,
    limit: int = 100,
    service: IngredientService = Depends(IngredientServiceFactory.inject),
) -> List[IngredientResponse]:
    return await service.list(skip, limit)


@router.get("/{ingredient_id}", response_model=IngredientResponse)
async def read_ingredient(
    ingredient_id: int,
    service: IngredientService = Depends(IngredientServiceFactory.inject),
) -> IngredientResponse:
    return await service.get(ingredient_id)


@router.patch(
    "/{ingredient_id}",
    response_model=IngredientResponse,
    dependencies=[Depends(get_current_user_id)],
)
async def update_ingredient(
    ingredient_id: int,
    obj_in: IngredientUpdate,
    service: IngredientService = Depends(IngredientServiceFactory.inject),
) -> IngredientResponse:
    return await service.update(ingredient_id, obj_in)


@router.delete(
    "/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user_id)],
)
async def delete_ingredient(
    ingredient_id: int,
    service: IngredientService = Depends(IngredientServiceFactory.inject),
) -> None:
    await service.delete(ingredient_id)
