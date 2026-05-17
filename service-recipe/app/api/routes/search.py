from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user_id
from app.services.search_service import search_service

router = APIRouter()

@router.get("/search/recipes")
async def search_recipe(
    current_user_id: str = Depends(get_current_user_id),
    q: Optional[str] = Query(None, description="Texte à rechercher (titre, description, ingrédients)"),
    difficulty: Optional[str] = Query(None, description="Niveau de difficulté (enum key)"),
    cuisine_origin: Optional[str] = Query(None, description="Origine culinaire (enum key)"),
    course_type: Optional[str] = Query(None, description="Type de plat (enum key)"),
    max_prep_time: Optional[int] = Query(None, ge=1, description="temps max de préparation"),
    exclude_allergens: Optional[list[str]] = Query(None, description="Allergène à exclure (enum key)"),
    exclude_diets: Optional[list[str]] = Query(None, description="Diet à exclure (enum key)"),
    exclude_nutrition: Optional[list[str]] = Query(None, description="Tag nutritionnels à exclure (enum key)"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
        Full-text recipe search scoped to the authenticated user.

        - q: searched in title (×3), description (×2), instructions, and ingredient names
        - difficulty: enum value, e.g. enums.difficulty.easy
        - exclude_allergens: repeated parameter, e.g. ?exclude_allergens=enums.allergen.gluten&exclude_allergens=enums.allergen.milk
        - max_prep_time: keeps only recipes where prep_time_minutes ≤ value
    """
    return await search_service.search_recipes(
        user_id=current_user_id,
        query=q,
        difficulty=difficulty,
        cuisine_origin=cuisine_origin,
        course_type=course_type,
        max_prep_time=max_prep_time,
        exclude_allergens=exclude_allergens,
        exclude_diets=exclude_diets,
        exclude_nutrition=exclude_nutrition,
        limit=limit,
        offset=offset,
    )