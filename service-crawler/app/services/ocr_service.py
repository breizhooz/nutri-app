from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps

from app.services.ocr_reading_order import ReadingOrder, TextBox

logger = logging.getLogger(__name__)

# Au-delà, on redimensionne avant l'OCR : sur une photo 4000 px (CPU) le gain de
# temps est net pour une précision quasi identique.
MAX_DIMENSION = 2000

# Moteur RapidOCR partagé (chargement des modèles ONNX → une seule fois par process).
_engine = None


class OcrError(Exception):
    """Raised when OCR cannot extract usable text from an image."""


def _get_engine():
    """Construit (ou réutilise) le moteur RapidOCR.

    Import paresseux : onnxruntime/opencv ne sont chargés qu'au premier OCR, pas
    au démarrage de l'app ni dans les tests unitaires. Modèles PP-OCRv6 par
    défaut, embarqués dans la roue ``rapidocr`` (aucun téléchargement).
    """
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR  # lazy import

        logger.info("Initialisation du moteur RapidOCR")
        _engine = RapidOCR(params={"Global.log_level": "warning"})
    return _engine


class OcrService:
    """Extracts raw text from an uploaded image using RapidOCR (deep learning,
    modèles PP-OCR exécutés par onnxruntime — pas Tesseract).

    L'image n'est jamais écrite sur disque : les octets sont décodés en mémoire
    (privacy : aucune persistance, aucun cache).
    """

    def __init__(self, reading_order: ReadingOrder | None = None) -> None:
        self._reading_order = reading_order or ReadingOrder()

    @staticmethod
    def _boxes_of(result) -> list:
        """Boîtes (4 points) du résultat RapidOCR ; ``None`` si rien n'est détecté."""
        return [] if result.boxes is None else list(result.boxes)

    @staticmethod
    def _preprocess(content: bytes) -> bytes:
        """Corrige l'orientation EXIF et borne la taille avant l'OCR.

        Renvoie le contenu d'origine tel quel si Pillow ne sait pas le décoder
        (le moteur OCR lèvera alors une erreur propre via OcrError).
        """
        try:
            with Image.open(io.BytesIO(content)) as im:
                im = ImageOps.exif_transpose(im)  # photo de téléphone souvent pivotée
                im = im.convert("RGB")
                longest = max(im.size)
                if longest > MAX_DIMENSION:
                    scale = MAX_DIMENSION / longest
                    im = im.resize((round(im.width * scale), round(im.height * scale)))
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=90)
                return buf.getvalue()
        except Exception as exc:
            logger.debug("Prétraitement image ignoré (%s), OCR sur l'original", exc)
            return content

    def extract_text_from_bytes(self, content: bytes) -> str:
        """OCR sur des octets image. Appel bloquant (offload via asyncio.to_thread)."""
        if not content:
            raise OcrError("Le fichier fourni est vide.")

        content = self._preprocess(content)
        try:
            result = _get_engine()(content)
        except Exception as exc:
            logger.error("RapidOCR a échoué : %s", exc)
            raise OcrError("Échec de l'analyse OCR de l'image.") from exc

        boxes = [
            TextBox.from_points(txt.strip(), points)
            for txt, points in zip(result.txts or (), self._boxes_of(result))
            if isinstance(txt, str) and txt.strip()
        ]
        text = "\n".join(self._reading_order.order(boxes)).strip()
        if not text:
            raise OcrError("Aucun texte n'a pu être extrait de l'image.")
        return text
