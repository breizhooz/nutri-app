import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.weekly_menu import WeeklyMenu
from app.models.menu_slot import MenuSlot
from app.schemas.weekly_menu import WeeklyMenuCreate, WeeklyMenuUpdate
from app.core.utils import slugify

async def _load_with_slots(session: AsyncSession, menu_id: int) -> WeeklyMenu | None:
    result = await session.execute(
        select(WeeklyMenu)
        .where(WeeklyMenu.id == menu_id)
        .options(selectinload(WeeklyMenu.slots))
    )

    return result.scalar_one_or_none()

async def _unique_slug(session: AsyncSession, start_date: date) -> str:
    base = slugify(f"menu-{start_date.strftime('%Y-%m-%d')}")
    slug = base
    i = 1
    while True:
        exist = await session.execute(select(WeeklyMenu).where(WeeklyMenu.slug == slug))
        if not exist.scalar_one_or_none():
            return slug
        if i > 99:
            return f"{base}-{uuid.uuid4().hex[:6]}"
        slug = f"{base} - {i}"
        i += 1

async def create_menu(
        session: AsyncSession,
        menu_data: WeeklyMenuCreate,
        user_id: str
) -> WeeklyMenu:
    slug = menu_data.slug or await _unique_slug(session, menu_data.start_date)

    menu = WeeklyMenu(
        slug=slug,
        user_id=user_id,
        nb_persons=menu_data.nb_persons,
        caloric_target=menu_data.caloric_target,
        start_date=menu_data.start_date,
        exclusions=[e.value for e in menu_data.exclusions],
        free_tags=menu_data.free_tags,
        notes=menu_data.notes,
        rating=menu_data.rating,
    )
    session.add(menu)
    await session.flush()

    for slot_data in menu_data.slots:
        session.add(MenuSlot(
            menu_id=menu.id,
            day_of_week=slot_data.day_of_week,
            meal_type=slot_data.meal_type,
            recipe_id=slot_data.recipe_id,
        ))

    await session.commit()
    return await _load_with_slots(session, menu.id)

async def get_menu(session: AsyncSession, menu_id: int) -> WeeklyMenu | None:
    return await _load_with_slots(session, menu_id)

async def get_menu_by_user(session: AsyncSession, user_id: str, skip: int = 0, limit: int = 20) -> list[WeeklyMenu]:
    result = await session.execute(
        select(WeeklyMenu)
        .where(WeeklyMenu.user_id == user_id)
        .options(selectinload(WeeklyMenu.slots))
        .offset(skip)
        .limit(limit)
        .order_by(WeeklyMenu.start_date.desc())
    )
    return list(result.scalars().all())


async def update_menu(
        session: AsyncSession,
        menu_id: str,
        menu_data: WeeklyMenuUpdate
) -> WeeklyMenu | None:
    menu = await _load_with_slots(session, menu_id)
    if not menu:
        return None
    
    update_fields = menu_data.model_dump(exclude_unset=True, exclude={"slots"})
    if "exclusions" in update_fields and menu_data.exclusions is not None:
        update_fields["exclusions"] = [e.value for e in menu_data.exclusions]
    
    for field, value in update_fields.items():
        setattr(menu, field, value)
    
    if menu_data.slots is not None:
        menu.slots.clear()
        for slot_data in menu_data.slots:
            menu.slots.append(MenuSlot(
                day_of_week=slot_data.day_of_week,
                meal_type=slot_data.meal_type,
                recipe_id=slot_data.recipe_id,
            ))

    await session.commit()
    return await _load_with_slots(session, menu_id)


async def delete_menu(session: AsyncSession, menu_id: int) -> bool:
    menu = await session.get(WeeklyMenu, menu_id)
    if not menu:
        return False
    await session.delete(menu)
    await session.commit()
    return True

