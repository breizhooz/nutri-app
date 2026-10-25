from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import case, false, func, literal, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_item import NutritionItem

# Similarité trigramme minimale pour qu'un aliment soit candidat (0..1).
_MIN_SIMILARITY = 0.5
# Sans mot de tête commun, il faut une correspondance quasi exacte : mieux vaut
# une MacroError visible qu'un faux ami (« crème fraîche » → « Criste marine, fraîche »).
_STRONG_SIMILARITY = 0.8
# Bonus quand un mot de la requête est la tête du nom Ciqual (l'aliment
# principal vient en premier : « Tomate, crue » plutôt que « Caviar de tomates »).
_HEAD_BONUS = 0.5
# Le nom anglais ne sert que de repli et compte moins que le nom français.
_EN_WEIGHT = 0.8

_WORD = re.compile(r"\w+")


@dataclass
class LookupResult:
    slug: str
    nom_fr: str
    calories: float
    proteines: float
    glucides: float
    lipides: float
    fibres: float | None
    score: float


def _normalized(expr):
    # f_unaccent (IMMUTABLE, migration e2f3a4b5c6d7) : mêmes expressions que les
    # index trigrammes, sinon le planificateur ne peut pas les utiliser.
    return func.f_unaccent(func.lower(expr))


def _head_pattern(query: str) -> str | None:
    """Regex « le nom commence par un des mots de la requête » (pluriel naïf).

    Mots de 3 lettres et plus : « de », « d' » ne sont jamais l'aliment principal.
    """
    stems = []
    for word in _WORD.findall(query.lower()):
        if len(word) < 3:
            continue
        stems.append(word[:-1] if len(word) > 3 and word[-1] in "sx" else word)
    if not stems:
        return None
    return r"^(" + "|".join(re.escape(stem) for stem in stems) + r")[sx]?\M"


class LookupService:
    """Fuzzy match PostgreSQL (pg_trgm + unaccent) sur le référentiel nutritionnel.

    Score = ``word_similarity(requête, nom)`` (meilleure correspondance de la
    requête avec un fragment du nom) + bonus si un mot de la requête est la
    tête du nom. À score égal, le nom le plus court (le plus générique) gagne.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, query: str, size: int = 5) -> list[LookupResult]:
        """Retourne les candidats acceptés, du meilleur au moins bon, ou liste vide."""
        term = _normalized(literal(query.strip()))
        name_fr = _normalized(NutritionItem.nom_fr)
        # '' en dur (pas en paramètre) : l'expression doit être celle de l'index.
        name_en = _normalized(func.coalesce(NutritionItem.nom_en, literal_column("''")))
        similarity_fr = func.word_similarity(term, name_fr)
        similarity_en = func.word_similarity(term, name_en) * _EN_WEIGHT
        pattern = _head_pattern(query)
        is_head = (
            name_fr.regexp_match(func.f_unaccent(literal(pattern)))
            if pattern
            else false()
        )
        score = func.greatest(
            similarity_fr + case((is_head, _HEAD_BONUS), else_=0.0),
            similarity_en,
        )
        accepted = or_(
            (similarity_fr >= _MIN_SIMILARITY)
            & ((similarity_fr >= _STRONG_SIMILARITY) | is_head),
            similarity_en >= _STRONG_SIMILARITY,
        )
        # Candidats lus via les index trigrammes : `requête <% nom` ⇔
        # word_similarity ≥ pg_trgm.word_similarity_threshold (fixé pour la transaction).
        candidate = or_(term.op("<%")(name_fr), term.op("<%")(name_en))
        await self._session.execute(
            select(
                func.set_config(
                    "pg_trgm.word_similarity_threshold", str(_MIN_SIMILARITY), True
                )
            )
        )
        stmt = (
            select(NutritionItem, score.label("score"))
            .where(candidate, accepted)
            .order_by(score.desc(), func.length(NutritionItem.nom_fr))
            .limit(size)
        )
        rows = (await self._session.execute(stmt)).all()

        return [
            LookupResult(
                slug=item.slug,
                nom_fr=item.nom_fr,
                calories=item.calories or 0.0,
                proteines=item.proteines or 0.0,
                glucides=item.glucides or 0.0,
                lipides=item.lipides or 0.0,
                fibres=item.fibres,
                score=float(row_score),
            )
            for item, row_score in rows
        ]
