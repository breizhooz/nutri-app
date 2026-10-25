"""Recherche de recettes — PostgreSQL plein texte (remplace Elasticsearch).

• Texte : ``recipes.search_vector`` (tsvector ``french`` désaccentué, pondéré
  titre A / ingrédients B / description C / instructions D, maintenu par
  triggers) interrogé en préfixe (« poul » trouve « poulet ») ; tolérance aux
  fautes de frappe sur le titre via ``pg_trgm.word_similarity``.
• Tags (allergènes, régimes, nutrition, types) : lus en direct sur les
  ingrédients de la recette — pas de copie à resynchroniser.
• Critères du moteur de cibles : exclusions éliminatoires + scoring de
  proximité des macros (décroissance gaussienne, ½ à ``target ± scale``).
"""

import logging
import re
from typing import Optional

from sqlalchemy import (
    ColumnElement,
    and_,
    case,
    exists,
    false,
    func,
    literal,
    not_,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import Allergen, Diet, Nutrition, TypeOfIngredient
from app.models.ingredient import Ingredient
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.schemas.search import SearchCriteria

logger = logging.getLogger(__name__)

TAG_MAPPING = {}
TAG_MAPPING.update({a.value: "allergens" for a in Allergen})
TAG_MAPPING.update({d.value: "diets" for d in Diet})
TAG_MAPPING.update({n.value: "nutrition" for n in Nutrition})
TAG_MAPPING.update({t.value: "types" for t in TypeOfIngredient})

_TS_CONFIG = "french"
# Similarité trigramme minimale requête ↔ titre pour rattraper une faute de frappe,
# seulement à partir de 4 caractères (en deçà, « de » matcherait tout titre en « de »).
_TITLE_SIMILARITY_MIN = 0.5
_TYPO_MIN_LENGTH = 4

# Champs de recette que le moteur de cibles peut exiger ou scorer
# (noms historiques des documents de recherche).
_FIELD_COLUMNS = {
    "calories": Recipe.calories_per_serving,
    "proteines": Recipe.proteins_per_serving,
    "glucides": Recipe.carbs_per_serving,
    "lipides": Recipe.fats_per_serving,
    "prep_time_minutes": Recipe.prep_time_minutes,
    "cook_time_minutes": Recipe.cook_time_minutes,
    "servings": Recipe.servings,
    "difficulty": Recipe.difficulty,
    "cuisine_origin": Recipe.cuisine_origin,
    "course_type": Recipe.course_type,
    "description": Recipe.description,
    "image_url": Recipe.image_url,
}

_WORD = re.compile(r"\w+")


def _unaccent_lower(expr) -> ColumnElement:
    return func.unaccent(func.lower(expr))


def _prefix_tsquery(query: str) -> str | None:
    """« Poulet curry » → ``poulet:* & curry:*`` (mots seuls : syntaxe sûre).

    Les fragments d'une lettre (« l' » de « l'huile ») sont ignorés : en préfixe
    ils correspondraient à presque tout.
    """
    words = [word for word in _WORD.findall(query) if len(word) > 1]
    if not words:
        return None
    return " & ".join(f"{word}:*" for word in words)


def _has_ingredient_matching(condition) -> ColumnElement:
    """Vrai si la recette contient au moins un ingrédient vérifiant ``condition``."""
    return exists(
        select(RecipeIngredient.id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == Recipe.id, condition)
    )


def _terms_pattern(terms: list[str]) -> str:
    """Regex PostgreSQL : un des termes en mot entier, pluriel naïf toléré
    (« lait » exclut « Lait entier » mais pas « laitue »)."""
    alternation = "|".join(re.escape(term.strip().lower()) for term in terms)
    return rf"\m({alternation})[sx]?\M"


def _column(field: str):
    column = _FIELD_COLUMNS.get(field)
    if column is None:
        logger.warning("Search criteria: unknown recipe field %r ignored", field)
    return column


class RecipeSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_recipes(
        self,
        account_id: str,
        query: Optional[str] = None,
        difficulty: Optional[str] = None,
        cuisine_origin: Optional[str] = None,
        course_type: Optional[str] = None,
        max_prep_time: Optional[int] = None,
        exclude_allergens: Optional[list[str]] = None,
        exclude_diets: Optional[list[str]] = None,
        exclude_nutrition: Optional[list[str]] = None,
        limit: int = 10,
        offset: int = 0,
        criteria: Optional[SearchCriteria] = None,
        apply_scoring: bool = True,
    ) -> dict:
        """Recherche bornée au compte actif (multicomptes : ``account_id``).

        ``criteria`` (moteur de cibles nutritionnelles) ajoute ses exclusions ;
        si ``apply_scoring``, ses cibles de macros et préférences pondèrent aussi
        le score (multiplié au score texte).
        """
        conditions = [Recipe.account_id == account_id]
        text_score: ColumnElement = literal(1.0)

        if query and query.strip():
            match, text_score = self._text_match(query.strip())
            conditions.append(match)

        # Enums str : la valeur d'API (« enums.difficulty.easy ») est convertie
        # par SQLAlchemy vers le nom stocké (« EASY »).
        if difficulty:
            conditions.append(Recipe.difficulty == difficulty)
        if cuisine_origin:
            conditions.append(Recipe.cuisine_origin == cuisine_origin)
        if course_type:
            conditions.append(Recipe.course_type == course_type)
        if max_prep_time is not None:
            conditions.append(Recipe.prep_time_minutes <= max_prep_time)

        excluded_tags = [
            *(exclude_allergens or []),
            *(exclude_diets or []),
            *(exclude_nutrition or []),
        ]
        score = text_score
        if criteria is not None:
            excluded_tags += criteria.excluded_tags
            conditions += self._criteria_conditions(criteria)
            if apply_scoring:
                nutrition_score = self._nutrition_score(criteria)
                if nutrition_score is not None:
                    score = text_score * nutrition_score

        if excluded_tags:
            conditions.append(
                not_(_has_ingredient_matching(Ingredient.tags.overlap(excluded_tags)))
            )

        where = and_(*conditions)
        total = await self._session.scalar(
            select(func.count()).select_from(Recipe).where(where)
        )
        scored = (
            await self._session.execute(
                select(Recipe.id, score.label("score"))
                .where(where)
                .order_by(score.desc(), Recipe.created_at.desc(), Recipe.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()

        recipes = await self._load(row.id for row in scored)
        results = [
            {"id": row.id, "score": float(row.score), **self._document(recipes[row.id])}
            for row in scored
            if row.id in recipes
        ]
        return {"total": total, "limit": limit, "offset": offset, "results": results}

    # ── Texte ───────────────────────────────────────────────────────────────
    @staticmethod
    def _text_match(query: str) -> tuple[ColumnElement, ColumnElement]:
        """Condition (plein texte OU titre approchant) + score texte."""
        title_similarity = func.word_similarity(
            _unaccent_lower(literal(query)), _unaccent_lower(Recipe.title)
        )
        typo_match = (
            title_similarity >= _TITLE_SIMILARITY_MIN
            if len(query) >= _TYPO_MIN_LENGTH
            else false()
        )
        tsquery_text = _prefix_tsquery(query)
        if tsquery_text is None:
            return typo_match, title_similarity

        tsquery = func.to_tsquery(_TS_CONFIG, func.unaccent(literal(tsquery_text)))
        fulltext = Recipe.search_vector.op("@@")(tsquery)
        score = func.ts_rank(Recipe.search_vector, tsquery) + title_similarity
        return or_(fulltext, typo_match), score

    # ── Critères du moteur de cibles ────────────────────────────────────────
    @staticmethod
    def _criteria_conditions(criteria: SearchCriteria) -> list[ColumnElement]:
        conditions: list[ColumnElement] = []
        terms = [t for t in criteria.excluded_terms if t.strip()]
        if terms:
            conditions.append(
                not_(
                    _has_ingredient_matching(
                        _unaccent_lower(Ingredient.name).regexp_match(
                            func.unaccent(literal(_terms_pattern(terms)))
                        )
                    )
                )
            )
        for field in criteria.required_fields:
            column = _column(field)
            if column is not None:
                conditions.append(column.is_not(None))
        return conditions

    @staticmethod
    def _nutrition_score(criteria: SearchCriteria) -> ColumnElement | None:
        """Somme des proximités de macros + bonus des préférences renseignées.

        Une recette sans macro renseignée ne marque pas de point sur ce critère.
        """
        parts: list[ColumnElement] = []
        for target in criteria.macro_targets:
            column = _column(target.field)
            if column is None:
                continue
            distance = (column - target.target) / target.scale
            parts.append(func.coalesce(func.power(0.5, distance * distance), 0.0))
        for preference in criteria.preferences:
            column = _column(preference.field)
            if column is None:
                continue
            parts.append(case((column.is_not(None), preference.weight), else_=0.0))
        if not parts:
            return None
        total = parts[0]
        for part in parts[1:]:
            total = total + part
        return total

    # ── Documents de résultat ───────────────────────────────────────────────
    async def _load(self, ids) -> dict[int, Recipe]:
        ids = list(ids)
        if not ids:
            return {}
        result = await self._session.execute(
            select(Recipe)
            .where(Recipe.id.in_(ids))
            .options(
                selectinload(Recipe.recipe_ingredients).selectinload(
                    RecipeIngredient.ingredient
                )
            )
        )
        return {recipe.id: recipe for recipe in result.scalars()}

    @staticmethod
    def _document(recipe: Recipe) -> dict:
        """Résultat de recherche (forme inchangée depuis la bascule depuis ES)."""
        ingredient_names = []
        extracted_tags = {
            "allergens": set(),
            "diets": set(),
            "nutrition": set(),
            "types": set(),
        }
        for ri in recipe.recipe_ingredients or []:
            if ri.ingredient:
                ingredient_names.append(ri.ingredient.name)
                for tag in ri.ingredient.tags or []:
                    category = TAG_MAPPING.get(tag)
                    if category:
                        extracted_tags[category].add(tag)

        doc = {
            "title": recipe.title,
            "slug": recipe.slug,
            "description": recipe.description,
            "instructions": recipe.instructions,
            "difficulty": recipe.difficulty.value if recipe.difficulty else None,
            "cuisine_origin": recipe.cuisine_origin.value
            if recipe.cuisine_origin
            else None,
            "origin_recipe": recipe.origin_recipe.value
            if recipe.origin_recipe
            else None,
            "course_type": recipe.course_type.value if recipe.course_type else None,
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "servings": recipe.servings,
            "ingredient_names": ingredient_names,
            "image_url": recipe.image_url,
            "free_tags": recipe.free_tags or [],
            "account_id": recipe.account_id,
            # Coaching : provenance d'un push coach→client (cf. coaching_model.md
            # §6) → l'UI badge « Ajouté par votre gestionnaire » sur la grille.
            "source_recipe_id": recipe.source_recipe_id,
            "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
            # Macros par portion — noms alignés sur le moteur de cibles (fr).
            "calories": recipe.calories_per_serving,
            "proteines": recipe.proteins_per_serving,
            "glucides": recipe.carbs_per_serving,
            "lipides": recipe.fats_per_serving,
        }
        for category, tags in extracted_tags.items():
            doc[category] = sorted(tags)
        return doc
