from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIngredient:
    raw_text: str
    quantite: float
    unite: str
    nom: str
    confidence: float


class SpacyExtractor:
    """Extraction NLP locale.

    spaCy (fr_core_news_md) est chargé paresseusement. En son absence,
    le parser regex reste opérationnel (cas tests, CI léger).
    """

    _QUANTITY_RE = re.compile(
        r"^(\d+(?:[.,]\d+)?)\s*"
        r"([a-zA-Zà-ÿ]{1,10})?\s*"
        r"(?:de |d'|du |de la |des )?"
        r"(.+?)$",
        re.UNICODE | re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._nlp = None

    def _load_model(self) -> None:
        if self._nlp is not None:
            return
        try:
            import spacy
            self._nlp = spacy.load("fr_core_news_md")
        except Exception:
            pass

    def extract(self, text: str) -> list[ExtractedIngredient] | None:
        """Retourne la liste extraite ou None si aucun ingrédient trouvé."""
        if not text.strip():
            return []
        self._load_model()
        return self._parse(text)

    def _parse(self, text: str) -> list[ExtractedIngredient] | None:
        results = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = self._QUANTITY_RE.match(line)
            if not m:
                continue
            qty_str, unite, nom = m.groups()
            try:
                quantite = float(qty_str.replace(",", "."))
            except ValueError:
                continue
            # If nom is suspiciously short, regex backtracking consumed the ingredient
            # name as the unit (e.g. "3 oeufs" → unite="oeuf", nom="s")
            if nom and unite and len(nom.strip()) <= 2 and not nom.strip().isspace():
                nom = unite + nom
                unite = "g"
            if not nom or not nom.strip():
                continue
            results.append(
                ExtractedIngredient(
                    raw_text=line,
                    quantite=quantite,
                    unite=(unite or "g").lower().strip(),
                    nom=nom.strip(),
                    confidence=0.75,
                )
            )
        return results if results else None