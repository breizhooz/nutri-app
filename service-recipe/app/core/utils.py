import re

from nutri_shared.core.utils import slugify

__all__ = ["slugify", "normalize_keyword"]


def normalize_keyword(keyword: str) -> str:
    """Normalise un mot-clé de recherche d'images pour servir de clé de cache.

    Minuscule, sans espaces de bord, espaces internes compactés — de sorte que
    « Tarte aux Pommes » et «  tarte   aux pommes » partagent la même entrée.
    """
    return re.sub(r"\s+", " ", (keyword or "").strip().lower())
