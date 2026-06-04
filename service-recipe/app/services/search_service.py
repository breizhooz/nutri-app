from typing import Optional
from elasticsearch import NotFoundError

import app.core.elasticsearch as _es_module
from app.core.config import settings
from app.models.enums import Allergen, TypeOfIngredient, Nutrition, Diet

TAG_MAPPING = {}
TAG_MAPPING.update({a.value: "allergens" for a in Allergen})
TAG_MAPPING.update({d.value: "diets" for d in Diet})
TAG_MAPPING.update({n.value: "nutrition" for n in Nutrition})
TAG_MAPPING.update({t.value: "types" for t in TypeOfIngredient})


class RecipeSearchService:
    def __init__(self):
        self.index_name = settings.ELASTICSEARCH_INDEX_RECIPES

    def _build_document(self, recipe) -> dict:
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
            "created_by_user_id": recipe.created_by_user_id,
            "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
            # Macros par portion — noms alignés sur le moteur de cibles (fr).
            "calories": recipe.calories_per_serving,
            "proteines": recipe.proteins_per_serving,
            "glucides": recipe.carbs_per_serving,
            "lipides": recipe.fats_per_serving,
        }

        for category, tags in extracted_tags.items():
            doc[category] = list(tags)

        return doc

    async def index_recipe(self, recipe) -> None:
        """
        create index or update into ES
        """
        await _es_module.es_client.index(
            index=self.index_name, id=recipe.id, document=self._build_document(recipe)
        )

    async def delete_recipe(self, recipe_id: int) -> None:
        """
        Delete one recipe from index
        """
        try:
            await _es_module.es_client.delete(index=self.index_name, id=recipe_id)
        except NotFoundError:
            pass
        except Exception as e:
            print(f"ES delete error for recipe {recipe_id}: {e}")

    async def delete_by_user(self, user_id: str) -> None:
        """Remove all documents authored by ``user_id`` from the index."""
        await _es_module.es_client.delete_by_query(
            index=self.index_name,
            query={"term": {"created_by_user_id": user_id}},
            refresh=True,
            conflicts="proceed",
        )

    async def search_recipes(
        self,
        user_id: str,
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
        extra_must_not: Optional[list[dict]] = None,
        extra_filter: Optional[list[dict]] = None,
        scoring_functions: Optional[list[dict]] = None,
    ) -> dict:
        """Fulltext search scoped to the authenticated user.

        ``extra_must_not`` / ``extra_filter`` / ``scoring_functions`` permettent au
        moteur de cibles nutritionnelles (Étape 3) d'injecter ses clauses sans que
        ce service ne connaisse leur logique. Si ``scoring_functions`` est fourni,
        la requête bool est enveloppée dans un ``function_score``.
        """
        must_queries = []
        # ``created_by_user_id`` est mappé en keyword (cf. core/elasticsearch.py) :
        # on filtre sur le champ directement, surtout pas sur un sous-champ
        # ``.keyword`` inexistant (sinon le term ne matche aucun document).
        filter_queries = [{"term": {"created_by_user_id": user_id}}]
        must_not_queries = []

        if query:
            must_queries.append(
                {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "title^3",
                                        "description^2",
                                        "instructions",
                                        "ingredient_names",
                                    ],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO",
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^3", "ingredient_names^2"],
                                    "type": "phrase_prefix",
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        if difficulty:
            filter_queries.append({"term": {"difficulty": difficulty}})

        if cuisine_origin:
            filter_queries.append({"term": {"cuisine_origin": cuisine_origin}})

        if course_type:
            filter_queries.append({"term": {"course_type": course_type}})

        if max_prep_time is not None:
            filter_queries.append(
                {"range": {"prep_time_minutes": {"lte": max_prep_time}}}
            )

        exclusions = {
            "allergens": exclude_allergens,
            "diets": exclude_diets,
            "nutrition": exclude_nutrition,
        }

        for field_name, values in exclusions.items():
            if values:
                for value in values:
                    must_not_queries.append({"term": {field_name: value}})

        # Clauses injectées par le moteur de cibles nutritionnelles (Étape 3).
        if extra_must_not:
            must_not_queries.extend(extra_must_not)
        if extra_filter:
            filter_queries.extend(extra_filter)

        bool_query = {
            "bool": {
                "must": must_queries if must_queries else [{"match_all": {}}],
                "filter": filter_queries,
                "must_not": must_not_queries,
            }
        }

        if scoring_functions:
            inner_query = {
                "function_score": {
                    "query": bool_query,
                    "functions": scoring_functions,
                    "score_mode": "sum",
                    "boost_mode": "multiply",
                }
            }
        else:
            inner_query = bool_query

        es_query = {
            "query": inner_query,
            "from": offset,
            "size": limit,
            "sort": ["_score", {"created_at": "desc"}],
        }

        response = await _es_module.es_client.search(index=self.index_name, **es_query)

        hits = response["hits"]["hits"]
        results = [
            {
                "id": int(hit["_id"]),
                "score": hit["_score"],
                **{
                    k: v for k, v in hit["_source"].items() if k != "created_by_user_id"
                },
            }
            for hit in hits
        ]

        return {
            "total": response["hits"]["total"]["value"],
            "limit": limit,
            "offset": offset,
            "results": results,
        }

    async def reindex_all(self, session) -> int:
        """Bulk reindex all recipes from the database."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.recipe import Recipe
        from app.models.recipe_ingredients import RecipeIngredient

        result = await session.execute(
            select(Recipe).options(
                selectinload(Recipe.recipe_ingredients).selectinload(
                    RecipeIngredient.ingredient
                )
            )
        )
        recipes = result.scalars().all()
        for recipe in recipes:
            await self.index_recipe(recipe)
        return len(recipes)


search_service = RecipeSearchService()
