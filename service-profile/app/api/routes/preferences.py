import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, get_locale
from app.i18n import t
from app.db.session import get_session
from app.repositories.profile_repository import ProfileRepository
from app.schemas.preferences import (
    ExcludedFoodCreate, ExcludedFoodResponse,
    LifestyleProfileCreate, LifestyleProfileResponse,
    NutritionPreferencesCreate, NutritionPreferencesResponse,
    PerformanceMetricCreate, PerformanceMetricResponse,
    SportsProfileCreate, SportsProfileResponse,
)
from app.services.preferences_service import PreferencesService

router = APIRouter()


async def _require_profile_id(user_id: uuid.UUID, session: AsyncSession, locale: str) -> uuid.UUID:
    profile = await ProfileRepository(session).get_by_user_id(user_id)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("profile.not_found", locale))
    return profile.id


@router.put("/me/sports", response_model=SportsProfileResponse)
async def upsert_sports(
    request: Request,
    data: SportsProfileCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> SportsProfileResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).upsert_sports(profile_id, data)
    return SportsProfileResponse.model_validate(obj)


@router.get("/me/sports", response_model=SportsProfileResponse)
async def get_sports(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> SportsProfileResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).get_sports(profile_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("sports_profile.not_found", locale))
    return SportsProfileResponse.model_validate(obj)


@router.post("/me/performance", response_model=PerformanceMetricResponse, status_code=status.HTTP_201_CREATED)
async def add_performance(
    request: Request,
    data: PerformanceMetricCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> PerformanceMetricResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).add_performance(profile_id, data)
    return PerformanceMetricResponse.model_validate(obj)


@router.get("/me/performance", response_model=list[PerformanceMetricResponse])
async def list_performance(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[PerformanceMetricResponse]:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    items = await PreferencesService(session).list_performance(profile_id)
    return [PerformanceMetricResponse.model_validate(i) for i in items]


@router.delete("/me/performance/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    if not await PreferencesService(session).delete_performance(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("performance.not_found", locale))


@router.put("/me/lifestyle", response_model=LifestyleProfileResponse)
async def upsert_lifestyle(
    request: Request,
    data: LifestyleProfileCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> LifestyleProfileResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).upsert_lifestyle(profile_id, data)
    return LifestyleProfileResponse.model_validate(obj)


@router.get("/me/lifestyle", response_model=LifestyleProfileResponse)
async def get_lifestyle(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> LifestyleProfileResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).get_lifestyle(profile_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("lifestyle.not_found", locale))
    return LifestyleProfileResponse.model_validate(obj)


@router.put("/me/nutrition", response_model=NutritionPreferencesResponse)
async def upsert_nutrition(
    request: Request,
    data: NutritionPreferencesCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> NutritionPreferencesResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).upsert_nutrition(profile_id, data)
    return NutritionPreferencesResponse.model_validate(obj)


@router.get("/me/nutrition", response_model=NutritionPreferencesResponse)
async def get_nutrition(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> NutritionPreferencesResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).get_nutrition(profile_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("nutrition.not_found", locale))
    return NutritionPreferencesResponse.model_validate(obj)


@router.post("/me/excluded-foods", response_model=ExcludedFoodResponse, status_code=status.HTTP_201_CREATED)
async def add_excluded_food(
    request: Request,
    data: ExcludedFoodCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ExcludedFoodResponse:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    obj = await PreferencesService(session).add_excluded_food(profile_id, data)
    return ExcludedFoodResponse.model_validate(obj)


@router.get("/me/excluded-foods", response_model=list[ExcludedFoodResponse])
async def list_excluded_foods(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[ExcludedFoodResponse]:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    items = await PreferencesService(session).list_excluded_foods(profile_id)
    return [ExcludedFoodResponse.model_validate(i) for i in items]


@router.delete("/me/excluded-foods/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_excluded_food(
    request: Request,
    slug: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    locale = get_locale(request)
    profile_id = await _require_profile_id(user_id, session, locale)
    if not await PreferencesService(session).delete_excluded_food(slug, profile_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=t.get("excluded_food.not_found", locale))