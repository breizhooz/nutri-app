import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import verify_service_token
from app.db.session import get_session
from app.i18n.loader import t
from app.schemas.calculate import (
    CalculateRequest,
    CalculateResponse,
    ErrorIngredient,
    MacroValues,
    ResolvedIngredient,
)
from app.services.extraction_service import ExtractionService
from app.services.macro_calculator import MacroCalculator

router = APIRouter()


@router.post("", response_model=CalculateResponse)
async def calculate_macros(
    payload: CalculateRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_service_token),
) -> CalculateResponse:
    """Calcule les macros d'une recette (appel inter-service)."""
    try:
        user_id = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("errors.invalid_payload"),
        )

    if not payload.ingredients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=t.get("extraction.no_ingredients"),
        )

    result = await ExtractionService(session).process(
        raw_texts=[ing.raw_text for ing in payload.ingredients],
        user_id=user_id,
    )

    ingredient_macros = [
        MacroCalculator.compute_ingredient_macros(
            nutrition_item_slug=r.matched.slug,
            grammes=r.grammes,
            cal_100=r.matched.calories,
            prot_100=r.matched.proteines,
            gluc_100=r.matched.glucides,
            lipid_100=r.matched.lipides,
            raw_text=r.raw_text,
        )
        for r in result.resolved
    ]

    total, per_serving = MacroCalculator().calculate(ingredient_macros, payload.servings)

    return CalculateResponse(
        recipe_slug=payload.recipe_slug,
        servings=payload.servings,
        total=MacroValues(
            calories=total.calories,
            proteines=total.proteines,
            glucides=total.glucides,
            lipides=total.lipides,
        ),
        per_serving=MacroValues(
            calories=per_serving.calories,
            proteines=per_serving.proteines,
            glucides=per_serving.glucides,
            lipides=per_serving.lipides,
        ),
        resolved=[
            ResolvedIngredient(
                raw_text=im.raw_text,
                matched_slug=im.matched_slug,
                grammes=im.grammes,
                macros=MacroValues(
                    calories=im.calories,
                    proteines=im.proteines,
                    glucides=im.glucides,
                    lipides=im.lipides,
                ),
            )
            for im in ingredient_macros
        ],
        errors=[
            ErrorIngredient(
                raw_text=f.raw_text,
                slug=f.macro_error_slug,
                suggested=f.suggested,
            )
            for f in result.failed
        ],
    )