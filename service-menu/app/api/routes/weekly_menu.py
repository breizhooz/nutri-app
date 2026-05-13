from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.db.session import get_session
from app.core.deps import get_current_user_id
from app.core.http_client import ServicesRecipeClient, get_recipe_client, ServiceUnavailableError
from app.schemas.weekly_menu import WeeklyMenuCreate, WeeklyMenuUpdate, WeeklyMenuResponse
from app.repositories import menu_service
from app.services.randomizer import generate_slots
from app.i18n import LocalizedHTTPException

router = APIRouter()

@router.post("", response_model=WeeklyMenuResponse, status_code=status.HTTP_201_CREATED)
async def create_menu(
        menu_data: WeeklyMenuCreate,
        session: AsyncSession = Depends(get_session),
        current_user_id: str = Depends(get_current_user_id)
):
    return await menu_service.create_menu(session, menu_data=menu_data, user_id=current_user_id)

@router.post("/generate", response_model=WeeklyMenuResponse, status_code=status.HTTP_201_CREATED)
async def generate_menu(
    menu_data: WeeklyMenuCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    recipe_client: ServicesRecipeClient = Depends(get_recipe_client),
    current_user_id: str = Depends(get_current_user_id)
):
    try:
        menu_data.slots = await generate_slots(
            recipe_client=recipe_client,
            nb_persons=menu_data.nb_persons,
            start_date=menu_data.start_date,
            exclusions=menu_data.exclusions,
            caloric_target=menu_data.caloric_target,
        )
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_recipe_unavailable(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return await menu_service.create_menu(session, menu_data, current_user_id)

@router.get("", response_model=list[WeeklyMenuResponse])
async def list_menus(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    return await menu_service.get_menu_by_user(session, current_user_id, skip, limit)


@router.get("/{menu_id}", response_model=WeeklyMenuResponse)
async def get_menu(
    menu_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.user_id != current_user_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    return menu


@router.put("/{menu_id}", response_model=WeeklyMenuResponse)
async def update_menu(
    menu_id: int,
    menu_data: WeeklyMenuUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.user_id != current_user_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    return await menu_service.update_menu(session, menu_id, menu_data)


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu(
    menu_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.user_id != current_user_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    await menu_service.delete_menu(session, menu_id)