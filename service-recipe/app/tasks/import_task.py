import asyncio
import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.import_task.import_recipes_payload")
def import_recipes_payload(
    raw_payload: dict, notify_user_id: str | None = None
) -> dict:
    """Import en masse de recettes (+ catalogue d'ingrédients) en tâche de fond.

    ``raw_payload`` est le contenu JSON déjà validé par la route ; on le re-valide
    ici par sécurité (le worker est le dernier rempart). Les macros sont calculées
    via service-nutrition, l'indexation Elasticsearch est best-effort.

    ``notify_user_id`` (l'admin déclencheur) reçoit une notification in-app de fin
    ou d'échec via service-notification (best-effort). En cas d'erreur, on notifie
    puis on relance l'exception pour que Celery marque la tâche FAILURE.

    Retourne le rapport d'import sérialisable consommé par le polling du front.
    """

    async def _run() -> dict:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.core import elasticsearch as es_module
        from app.core.elasticsearch import init_elasticsearch
        from app.repositories.recipe_repository import RecipeRepository
        from app.schemas.recipe_import import RecipeImportPayload
        from app.services.recipe_import_service import RecipeImportService
        from app.services.recipe_service import RecipeService
        from app.services.search_service import search_service

        payload = RecipeImportPayload.model_validate(raw_payload)

        es_ready = False
        try:
            await init_elasticsearch()
            es_ready = True
        except Exception as exc:
            logger.warning(
                "Elasticsearch indisponible, indexation ignorée (%s). "
                "Lancez une réindexation plus tard.",
                exc,
            )

        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                repository = RecipeRepository(session)
                recipe_service = RecipeService(repository, search_service)
                import_service = RecipeImportService(repository, recipe_service)
                report = await import_service.import_payload(payload)
        finally:
            await engine.dispose()
            if es_ready and es_module.es_client is not None:
                await es_module.es_client.close()

        return {
            "ingredients_upserted": report.ingredients_upserted,
            "recipes_created": report.recipes_created,
            "recipe_slugs": report.recipe_slugs,
        }

    async def _notify_done(result: dict) -> None:
        if not notify_user_id:
            return
        from app.services.notification_client import NotificationClient

        await NotificationClient().notify_import_done(
            notify_user_id,
            recipes_created=result["recipes_created"],
            ingredients_upserted=result["ingredients_upserted"],
        )

    async def _notify_error(message: str) -> None:
        if not notify_user_id:
            return
        from app.services.notification_client import NotificationClient

        await NotificationClient().notify_import_error(notify_user_id, message)

    async def _run_and_notify() -> dict:
        try:
            result = await _run()
        except Exception as exc:
            # Notification best-effort, puis on relance pour marquer FAILURE.
            await _notify_error(f"L'import a échoué : {exc}")
            raise
        await _notify_done(result)
        return result

    result = asyncio.run(_run_and_notify())
    logger.info(
        "Import recettes terminé : %d ingrédient(s), %d recette(s).",
        result["ingredients_upserted"],
        result["recipes_created"],
    )
    return result
