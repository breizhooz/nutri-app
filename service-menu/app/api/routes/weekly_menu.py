from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from nutri_shared.core.context import AccessContext

from app.db.session import get_session
from app.core.deps import (
    get_read_account_id,
    get_write_account_id,
    get_write_context,
)
from app.core.http_client import (
    ServicesProfileClient,
    ServicesRecipeClient,
    get_profile_client,
    get_recipe_client,
    ServiceUnavailableError,
)
from app.schemas.weekly_menu import (
    WeeklyMenuCreate,
    WeeklyMenuUpdate,
    WeeklyMenuResponse,
)
from app.repositories import menu_service
from app.services.profile_constraints import build_constraints
from app.services.randomizer import generate_slots
from app.i18n import LocalizedHTTPException

router = APIRouter()


@router.post("", response_model=WeeklyMenuResponse, status_code=status.HTTP_201_CREATED)
async def create_menu(
    menu_data: WeeklyMenuCreate,
    session: AsyncSession = Depends(get_session),
    ctx: AccessContext = Depends(get_write_context),
):
    return await menu_service.create_menu(
        session, menu_data=menu_data, user_id=ctx.sub, account_id=ctx.account_id
    )


@router.post(
    "/generate", response_model=WeeklyMenuResponse, status_code=status.HTTP_201_CREATED
)
async def generate_menu(
    menu_data: WeeklyMenuCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    recipe_client: ServicesRecipeClient = Depends(get_recipe_client),
    profile_client: ServicesProfileClient = Depends(get_profile_client),
    ctx: AccessContext = Depends(get_write_context),
):
    # Contraintes du profil (allergies, aliments exclus, régime, cible
    # calorique). Fail-closed : service-profile en erreur → 503, plutôt que de
    # générer un menu qui ignore des allergies déclarées. Pas de profil (404)
    # ou intégration désactivée → contraintes vides. Les exclusions du payload
    # restent les seules persistées sur le menu ; celles du profil sont
    # réappliquées dynamiquement à chaque génération.
    try:
        summary = await profile_client.get_nutrition_summary(ctx.sub)
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_profile_unavailable(request)
    constraints = build_constraints(summary)

    if menu_data.caloric_target is None:
        menu_data.caloric_target = constraints.target_calories

    try:
        menu_data.slots = await generate_slots(
            recipe_client=recipe_client,
            nb_persons=menu_data.nb_persons,
            start_date=menu_data.start_date,
            exclusions=menu_data.exclusions,
            caloric_target=menu_data.caloric_target,
            constraints=constraints,
        )
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_recipe_unavailable(request)
    except ValueError:
        raise LocalizedHTTPException.no_recipes_available(request)

    existing = await menu_service.get_menu_by_account_and_date(
        session, ctx.account_id, menu_data.start_date
    )
    if existing:
        return await menu_service.update_menu(
            session,
            existing.id,
            WeeklyMenuUpdate(
                slots=menu_data.slots,
                caloric_target=menu_data.caloric_target,
                nb_persons=menu_data.nb_persons,
            ),
        )

    return await menu_service.create_menu(
        session, menu_data, user_id=ctx.sub, account_id=ctx.account_id
    )


@router.get("", response_model=list[WeeklyMenuResponse])
async def list_menus(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    account_id: str = Depends(get_read_account_id),
):
    return await menu_service.get_menu_by_account(session, account_id, skip, limit)


@router.get("/{menu_id}", response_model=WeeklyMenuResponse)
async def get_menu(
    menu_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    account_id: str = Depends(get_read_account_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.account_id != account_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    return menu


@router.put("/{menu_id}", response_model=WeeklyMenuResponse)
async def update_menu(
    menu_id: int,
    menu_data: WeeklyMenuUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    account_id: str = Depends(get_write_account_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.account_id != account_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    return await menu_service.update_menu(session, menu_id, menu_data)


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu(
    menu_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    account_id: str = Depends(get_write_account_id),
):
    menu = await menu_service.get_menu(session, menu_id)
    if not menu:
        raise LocalizedHTTPException.menu_not_found(request)
    if menu.account_id != account_id:
        raise LocalizedHTTPException.menu_unauthorized(request)
    await menu_service.delete_menu(session, menu_id)
