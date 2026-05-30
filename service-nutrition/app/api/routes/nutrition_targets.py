"""Route d'orchestration du moteur de cibles nutritionnelles.

Orchestration PURE : enchaîne les 3 étapes découplées sans aucune logique
nutritionnelle propre. Appel inter-service (token de service).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import verify_service_token
from app.schemas.engine import NutritionTargetsRequest, NutritionTargetsResponse
from app.services.engine.step1_base_targets import BaseTargetsCalculator
from app.services.engine.step2_user_overrides import UserOverridesService
from app.services.engine.step3_search_query import SearchQueryBuilder

router = APIRouter()


@router.post("", response_model=NutritionTargetsResponse)
async def compute_nutrition_targets(
    payload: NutritionTargetsRequest,
    _: None = Depends(verify_service_token),
) -> NutritionTargetsResponse:
    """Calcule les cibles finales sécurisées et la requête de recherche associée."""
    try:
        base = BaseTargetsCalculator().calculate(
            goal=payload.goal,
            diet_type=payload.diet_type,
            tdee_kcal=payload.tdee_kcal,
            bmr_kcal=payload.bmr_kcal,
            weight_kg=payload.weight_kg,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    final = UserOverridesService().apply(
        base=base,
        profile=payload.adjustment,
        goal=payload.goal,
        tdee_kcal=payload.tdee_kcal,
        bmr_kcal=payload.bmr_kcal,
        weight_kg=payload.weight_kg,
    )

    search_query = SearchQueryBuilder().build(
        targets=final,
        excluded_foods=payload.excluded_foods,
        diet_type=payload.diet_type,
        medical_contraindications=payload.medical_contraindications,
    )

    return NutritionTargetsResponse(targets=final, search_query=search_query)
