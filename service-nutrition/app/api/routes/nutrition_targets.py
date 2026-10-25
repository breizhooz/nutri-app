"""Route du moteur de cibles nutritionnelles.

Orchestration PURE : cibles reçues (calculées sur l'appareil ou fixées par un
coach) → ajustements UI (Étape 2) → critères de recherche (Étape 3). Aucune
donnée corporelle ni médicale. Appel inter-service (token de service).
"""

from fastapi import APIRouter, Depends

from app.core.deps import verify_service_token
from app.schemas.engine import NutritionTargetsRequest, NutritionTargetsResponse
from app.services.engine.step2_user_overrides import UserOverridesService
from app.services.engine.step3_search_query import SearchQueryBuilder

router = APIRouter()


@router.post("", response_model=NutritionTargetsResponse)
async def compute_nutrition_targets(
    payload: NutritionTargetsRequest,
    _: None = Depends(verify_service_token),
) -> NutritionTargetsResponse:
    """Applique les ajustements UI aux cibles reçues et en déduit les critères."""
    final = UserOverridesService().apply(payload.targets, payload.adjustment)
    search_criteria = SearchQueryBuilder().build(
        targets=final,
        excluded_foods=payload.excluded_foods,
        diet_type=payload.diet_type,
    )
    return NutritionTargetsResponse(targets=final, search_criteria=search_criteria)
