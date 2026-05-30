from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Au-delà, on redimensionne avant l'OCR : EasyOCR sur une photo 4000 px (CPU) prend
# ~38 s ; à 2000 px c'est ~3x plus rapide pour une précision quasi identique.
MAX_DIMENSION = 2000

# Lecteur EasyOCR partagé (chargement des modèles coûteux → une seule fois par process).
_reader = None
_reader_langs: tuple[str, ...] | None = None


class OcrError(Exception):
    """Raised when OCR cannot extract usable text from an image."""


def _get_reader(langs: tuple[str, ...]):
    """Construit (ou réutilise) le lecteur EasyOCR pour ces langues.

    L'import d'``easyocr`` (et donc de torch) est paresseux : il n'est payé qu'au
    premier OCR, pas au démarrage de l'app ni dans les tests unitaires.
    """
    global _reader, _reader_langs
    if _reader is None or _reader_langs != langs:
        import easyocr  # lazy import (torch lourd)

        logger.info("Initialisation du lecteur EasyOCR (langs=%s)", langs)
        _reader = easyocr.Reader(list(langs), gpu=False)
        _reader_langs = langs
    return _reader


class OcrService:
    """Extracts raw text from an uploaded image using EasyOCR (deep learning).

    L'image n'est jamais écrite sur disque : les octets sont décodés en mémoire
    par EasyOCR (privacy : aucune persistance, aucun cache).
    """

    # EasyOCR : le français et l'anglais (alphabet latin) sont combinables.
    DEFAULT_LANGS: tuple[str, ...] = ("fr", "en")

    def __init__(self, langs: tuple[str, ...] | None = None) -> None:
        self._langs = tuple(langs) if langs else self.DEFAULT_LANGS

    @staticmethod
    def _preprocess(content: bytes) -> bytes:
        """Corrige l'orientation EXIF et borne la taille avant l'OCR.

        Renvoie le contenu d'origine tel quel si Pillow ne sait pas le décoder
        (EasyOCR lèvera alors une erreur propre via OcrError).
        """
        try:
            with Image.open(io.BytesIO(content)) as im:
                im = ImageOps.exif_transpose(im)  # photo de téléphone souvent pivotée
                im = im.convert("RGB")
                longest = max(im.size)
                if longest > MAX_DIMENSION:
                    scale = MAX_DIMENSION / longest
                    im = im.resize(
                        (round(im.width * scale), round(im.height * scale))
                    )
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
            reader = _get_reader(self._langs)
            # detail=0 → liste de chaînes ; paragraph=True → regroupe les lignes.
            lines = reader.readtext(content, detail=0, paragraph=True)
        except Exception as exc:
            logger.error("EasyOCR a échoué : %s", exc)
            raise OcrError("Échec de l'analyse OCR de l'image.") from exc

        text = "\n".join(
            line.strip() for line in lines if isinstance(line, str) and line.strip()
        ).strip()
        if not text:
            raise OcrError("Aucun texte n'a pu être extrait de l'image.")
        return text
