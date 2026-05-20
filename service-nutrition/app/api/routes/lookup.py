from fastapi import APIRouter, Query

from app.schemas.calculate import LookupResponse
from app.services.lookup_service import LookupService

router = APIRouter()


@router.get("", response_model=list[LookupResponse])
async def lookup_item(
    q: str = Query(..., min_length=2, description="Nom d'ingrédient à chercher"),
) -> list[LookupResponse]:
    """Fuzzy match d'un aliment dans le référentiel nutritionnel."""
    results = await LookupService().search(q)
    return [
        LookupResponse(
            slug=r.slug,
            nom_fr=r.nom_fr,
            nom_en=None,
            calories=r.calories,
            proteines=r.proteines,
            glucides=r.glucides,
            lipides=r.lipides,
            fibres=r.fibres,
            score=r.score,
        )
        for r in results
    ]