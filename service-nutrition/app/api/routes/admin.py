from fastapi import APIRouter, Depends

from app.core.deps import verify_service_token
from app.tasks.nutrition_task import import_ciqual

router = APIRouter(tags=["admin"])


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
