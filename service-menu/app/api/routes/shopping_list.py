import csv
import io
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.db.session import get_session
from app.core.deps import get_current_user_id
from app.core.http_client import ServicesRecipeClient, get_recipe_client, ServiceUnavailableError
from app.schemas.shopping_list import ShoppingList
from app.repositories.menu_service import get_menu
from app.services.shopping_list_service import build_shopping_list
from app.services.export_service import export_shopping_list
from app.i18n import LocalizedHTTPException

router = APIRouter()

async def _resolve_shopping_list(
    menu_id: int,
    request: Request,
    session: AsyncSession,
    recipe_client: ServicesRecipeClient,
    user_id: str,
) -> ShoppingList:
    menu = await get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.user_id != user_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    try:
        return await build_shopping_list(menu, recipe_client)
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_recipe_unavailable(request)


@router.get("/{menu_id}/shopping-list", response_model=ShoppingList)
async def get_shopping_list(
    menu_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    recipe_client: ServicesRecipeClient = Depends(get_recipe_client),
    current_user_id: str = Depends(get_current_user_id),
):
    return await _resolve_shopping_list(menu_id, request, session, recipe_client, current_user_id)


@router.get("/{menu_id}/shopping-list/export")
async def export(
    menu_id: int,
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    session: AsyncSession = Depends(get_session),
    recipe_client: ServicesRecipeClient = Depends(get_recipe_client),
    current_user_id: str = Depends(get_current_user_id),
):
    sl = await _resolve_shopping_list(menu_id, request, session, recipe_client, current_user_id)
    return export_shopping_list(sl, format)