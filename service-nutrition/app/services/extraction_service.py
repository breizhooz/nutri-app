from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.macro_error_repository import MacroErrorRepository
from app.services.groq_extractor import GroqExtractor
from app.services.lookup_service import LookupResult, LookupService
from app.services.spacy_extractor import SpacyExtractor
from app.services.unit_converter import UnitConverter

logger = logging.getLogger(__name__)


@dataclass
class ResolvedIngredient:
    raw_text: str
    matched: LookupResult
    grammes: float


@dataclass
class FailedIngredient:
    raw_text: str
    macro_error_slug: str
    suggested: str | None


@dataclass
class ExtractionResult:
    resolved: list[ResolvedIngredient]
    failed: list[FailedIngredient]


class ExtractionService:
    """Orchestre l'escalier spaCy → Groq → MacroError pour chaque ingrédient brut."""

    def __init__(
        self,
        session: AsyncSession,
        spacy: SpacyExtractor | None = None,
        groq: GroqExtractor | None = None,
        lookup: LookupService | None = None,
    ) -> None:
        self._error_repo = MacroErrorRepository(session)
        self._converter = UnitConverter(session)
        self._spacy = spacy or SpacyExtractor()
        self._groq = groq or GroqExtractor()
        self._lookup = lookup or LookupService()

    async def process(
        self,
        raw_texts: list[str],
        user_id: uuid.UUID,
        recipe_id: uuid.UUID | None = None,
    ) -> ExtractionResult:
        resolved: list[ResolvedIngredient] = []
        failed: list[FailedIngredient] = []

        for raw_text in raw_texts:
            extracted = self._spacy.extract(raw_text)

            if extracted is None:
                try:
                    extracted = await self._groq.extract(raw_text)
                except Exception as exc:
                    logger.warning("Groq failed for '%s': %s", raw_text, exc)
                    extracted = []

            if not extracted:
                error = await self._error_repo.create(
                    user_id=user_id,
                    raw_ingredient=raw_text,
                    recipe_id=recipe_id,
                )
                failed.append(FailedIngredient(
                    raw_text=raw_text,
                    macro_error_slug=error.slug,
                    suggested=None,
                ))
                continue

            ingredient = extracted[0]
            candidates = await self._lookup.search(ingredient.nom)

            if not candidates:
                error = await self._error_repo.create(
                    user_id=user_id,
                    raw_ingredient=raw_text,
                    recipe_id=recipe_id,
                    suggested_match=ingredient.nom,
                )
                failed.append(FailedIngredient(
                    raw_text=raw_text,
                    macro_error_slug=error.slug,
                    suggested=ingredient.nom,
                ))
                continue

            grammes = await self._converter.to_grammes(
                ingredient.quantite, ingredient.unite
            )
            if grammes is None:
                grammes = ingredient.quantite

            resolved.append(ResolvedIngredient(
                raw_text=raw_text,
                matched=candidates[0],
                grammes=grammes,
            ))

        return ExtractionResult(resolved=resolved, failed=failed)