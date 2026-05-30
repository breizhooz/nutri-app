from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user_id
from app.services.nutrition_rules_service import nutrition_rules_service

router = APIRouter()


@router.get("/search/recipes")
async def search_recipe(
    current_user_id: str = Depends(get_current_user_id),
    q: Optional[str] = Query(
        None, description="Texte à rechercher (titre, description, ingrédients)"
    ),
    difficulty: Optional[str] = Query(
        None, description="Niveau de difficulté (enum key)"
    ),
    cuisine_origin: Optional[str] = Query(
        None, description="Origine culinaire (enum key)"
    ),
    course_type: Optional[str] = Query(None, description="Type de plat (enum key)"),
    max_prep_time: Optional[int] = Query(
        None, ge=1, description="temps max de préparation"
    ),
    exclude_allergens: Optional[list[str]] = Query(
        None, description="Allergène à exclure (enum key)"
    ),
    exclude_diets: Optional[list[str]] = Query(
        None, description="Diet à exclure (enum key)"
    ),
    exclude_nutrition: Optional[list[str]] = Query(
        None, description="Tag nutritionnels à exclure (enum key)"
    ),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    apply_rules: bool = Query(
        True,
        description="Applique les règles nutritionnelles du user si elles sont activées",
    ),
    aggressiveness: Optional[float] = Query(
        None, ge=0.5, le=1.5, description="Intensité : 0.5 Doux / 1.0 Modéré / 1.5 Intense"
    ),
    variety_pct: Optional[float] = Query(
        None, ge=0.0, le=0.5, description="Tolérance variété sur les calories (ex: 0.10)"
    ),
    override_calories: Optional[int] = Query(
        None, ge=0, description="Override manuel des calories cibles"
    ),
    override_proteines: Optional[int] = Query(
        None, ge=0, description="Override manuel des protéines cibles (g)"
    ),
):
    """
    Full-text recipe search scoped to the authenticated user.

    - q: searched in title (×3), description (×2), instructions, and ingredient names
    - difficulty: enum value, e.g. enums.difficulty.easy
    - exclude_allergens: repeated parameter, e.g. ?exclude_allergens=enums.allergen.gluten&exclude_allergens=enums.allergen.milk
    - max_prep_time: keeps only recipes where prep_time_minutes ≤ value
    - apply_rules: si True (défaut) et que le user a activé ses règles nutritionnelles,
      la recherche est personnalisée via le moteur de cibles (sinon recherche standard)
    """
    return await nutrition_rules_service.search(
        user_id=current_user_id,
        apply_rules=apply_rules,
        aggressiveness=aggressiveness,
        variety_pct=variety_pct,
        override_calories=override_calories,
        override_proteines=override_proteines,
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
