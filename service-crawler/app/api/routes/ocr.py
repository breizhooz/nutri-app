import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.deps import get_current_user_id
from app.i18n.loader import t
from app.services.groq_recipe_extractor import GroqRecipeExtractor
from app.services.ocr_service import OcrError, OcrService
from tasks.ocr import process_ocr_recipe

logger = logging.getLogger(__name__)

router = APIRouter()

# 10 MB — large enough for a high-res book/screen photo, small enough to bound OCR cost.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class OcrServiceFactory:
    @staticmethod
    def inject() -> OcrService:
        return OcrService()


class GroqExtractorFactory:
    @staticmethod
    def inject() -> GroqRecipeExtractor:
        return GroqRecipeExtractor()


class OcrImportRequest(BaseModel):
    raw_text: str
    title: str = "Recette importée"


@router.post("", status_code=status.HTTP_200_OK)
async def ocr_recipe(
    file: UploadFile = File(...),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    ocr: OcrService = Depends(OcrServiceFactory.inject),
    extractor: GroqRecipeExtractor = Depends(GroqExtractorFactory.inject),
):
    """Analyse une image : OCR + lecture IA, **sans rien persister**.

    Renvoie le texte OCR brut (``raw_text``) et le verdict de l'IA
    (``is_recipe``, ``title``, ``recipe_confidence``) pour que l'utilisateur voie
    ce qui a été extrait et décide lui-même de l'importer (cf. ``/import``).

    L'image n'est jamais stockée : ses octets sont décodés en mémoire par EasyOCR
    et ne touchent jamais le disque (aucune persistance, aucun cache).
    """
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=t.get("ocr.errors.not_an_image"),
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("ocr.errors.empty_file"),
        )
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=t.get("ocr.errors.file_too_large"),
        )

    # OCR is blocking + deletes the temp image in its own `finally`.
    try:
        raw_text = await asyncio.to_thread(ocr.extract_text_from_bytes, content)
    except OcrError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    extracted = await extractor.extract(raw_text)
    return {
        "is_recipe": extracted.is_recipe,
        "title": extracted.title,
        "recipe_confidence": extracted.recipe_confidence,
        "raw_text": raw_text,
        "detail": (
            t.get("ocr.analyzed")
            if extracted.is_recipe
            else t.get("ocr.errors.not_a_recipe")
        ),
    }


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
async def import_ocr_recipe(
    data: OcrImportRequest,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Crée la pré-recette à partir du texte OCR validé par l'utilisateur.

    Décision explicite de l'utilisateur après avoir vu le texte extrait : enfile
    la création de la pré-recette (statut EN_ATTENTE), comme le flux Instagram.
    """
    text = data.raw_text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t.get("ocr.errors.empty_text"),
        )

    process_ocr_recipe.delay(
        user_id=str(current_user_id),
        raw_text=text,
        title=data.title.strip() or "Recette importée",
    )
    return {"detail": t.get("ocr.queued"), "queued": True}
