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


class RegexIngredientParser:
    """Extraction locale « quantité + unité + nom » par expression régulière.

    1re marche de l'escalier d'extraction (regex → Groq → MacroError) : rapide,
    gratuite, hors ligne. Renvoie ``None`` quand rien n'est reconnu, ce qui
    déclenche le repli Groq. (Ex-``SpacyExtractor`` : le modèle spaCy qu'il
    chargeait n'était jamais utilisé — retiré le 2026-09-30.)
    """

    _QUANTITY_RE = re.compile(
        r"^(\d+(?:[.,]\d+)?)\s*"
        r"([a-zA-Zà-ÿ]{1,10})?\s*"
        r"(?:de |d'|du |de la |des )?"
        r"(.+?)$",
        re.UNICODE | re.IGNORECASE,
    )

    def extract(self, text: str) -> list[ExtractedIngredient] | None:
        """Retourne la liste extraite ou None si aucun ingrédient trouvé."""
        if not text.strip():
            return []
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
