from fastapi import APIRouter, Depends

from app.core.deps import verify_service_token
from app.tasks.nutrition_task import import_ciqual, reindex_elasticsearch

router = APIRouter(tags=["admin"])


@router.post("/admin/reindex")
async def reindex(
    _: None = Depends(verify_service_token),
):
    """Force une réindexation Elasticsearch de tous les NutritionItems."""
    task = reindex_elasticsearch.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/admin/import-ciqual")
async def trigger_ciqual_import(
    _: None = Depends(verify_service_token),
):
    """
    Force un téléchargement + import Ciqual immédiat.
    Utile après une mise à jour de la table ANSES hors cycle mensuel.
    """
    task = import_ciqual.delay()
    return {"task_id": task.id, "status": "queued"}