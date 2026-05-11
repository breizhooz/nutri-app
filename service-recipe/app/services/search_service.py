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
            "types": set()
        }

        for ri in (recipe.recipe_ingredients or []):
            if ri.ingredient:
                ingredient_names.append(ri.ingredient.name)
                for tag in (ri.ingredient.tags or []):
                    category = TAG_MAPPING.get(tag)
                    if category:
                        extracted_tags[category].add(tag)

        doc = {
            "title":              recipe.title,
            "slug":               recipe.slug,
            "description":        recipe.description,
            "instructions":       recipe.instructions,
            "difficulty":         recipe.difficulty.value if recipe.difficulty else None,
            "cuisine_origin":     recipe.cuisine_origin.value if recipe.cuisine_origin else None,
            "origin_recipe":      recipe.origin_recipe.value if recipe.origin_recipe else None,
            "course_type":        recipe.course_type.value if recipe.course_type else None,
            "prep_time_minutes":  recipe.prep_time_minutes,
            "cook_time_minutes":  recipe.cook_time_minutes,
            "servings":           recipe.servings,
            "ingredient_names":   ingredient_names,
            "created_by_user_id": recipe.created_by_user_id,
            "created_at":         recipe.created_at.isoformat() if recipe.created_at else None,
        }

        for category, tags in extracted_tags.items():
            doc[category] = list(tags)

        return doc
    
    async def index_recipe(self, recipe) -> None:
        """
        create index or update into ES
        """
        await _es_module.es_client.index(
            index = self.index_name,
            id = recipe.id,
            document=self._build_document(recipe)
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
    
    async def search_recipes(
        self,
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
    ) -> dict:
        """fulltext without filter."""
        must_queries = []
        filter_queries = []
        must_not_queries = []

        if query:
            must_queries.append({
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description^2", "instructions", "ingredient_names"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            })

        if difficulty:
            filter_queries.append({"term": {"difficulty": difficulty}})

        if cuisine_origin:
            filter_queries.append({"term": {"cuisine_origin": cuisine_origin}})

        if course_type:
            filter_queries.append({"term": {"course_type": course_type}})

        if max_prep_time is not None:
            filter_queries.append({
                "range": {"prep_time_minutes": {"lte": max_prep_time}}
            })

        exclusions = {
            "allergens": exclude_allergens,
            "diets": exclude_diets,
            "nutrition": exclude_nutrition
        }

        for field_name, values in exclusions.items():
            if values:
                for value in values:
                    must_not_queries.append({"term": {field_name: value}})
        
        es_query = {
            "query": {
                "bool": {
                    "must":     must_queries if must_queries else [{"match_all": {}}],
                    "filter":   filter_queries,
                    "must_not": must_not_queries,
                }
            },
            "from": offset,
            "size": limit,
            "sort": ["_score", {"created_at": "desc"}],
        }

        response = await _es_module.es_client.search(index=self.index_name, **es_query)

        hits = response["hits"]["hits"]
        results = [
            {"id": int(hit["_id"]), "score": hit["_score"], **hit["_source"]}
            for hit in hits
        ]

        return {
            "total":   response["hits"]["total"]["value"],
            "limit":   limit,
            "offset":  offset,
            "results": results,
        }


search_service = RecipeSearchService()

    

