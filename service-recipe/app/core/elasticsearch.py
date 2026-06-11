from elasticsearch import AsyncElasticsearch
from app.core.config import settings

es_client: AsyncElasticsearch = None  # initialized in lifespan via init_elasticsearch()

# Champs macros (par portion) consommés par le scoring du moteur de cibles.
# Noms alignés sur la convention française du moteur (proteines/glucides/lipides).
MACRO_PROPERTIES = {
    "calories": {"type": "float"},
    "proteines": {"type": "float"},
    "glucides": {"type": "float"},
    "lipides": {"type": "float"},
}


async def init_elasticsearch():
    global es_client
    es_client = AsyncElasticsearch([settings.ELASTICSEARCH_URL])

    index_name = settings.ELASTICSEARCH_INDEX_RECIPES

    if not await es_client.indices.exists(index=index_name):
        await es_client.indices.create(
            index=index_name,
            settings={
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "french_analyzer": {"type": "standard", "stopwords": "_french_"}
                    }
                },
            },
            mappings={
                "properties": {
                    "title": {"type": "text", "analyzer": "french_analyzer"},
                    "slug": {"type": "keyword"},
                    "description": {"type": "text", "analyzer": "french_analyzer"},
                    "instructions": {"type": "text", "analyzer": "french_analyzer"},
                    "difficulty": {"type": "keyword"},
                    "cuisine_origin": {"type": "keyword"},
                    "origin_recipe": {"type": "keyword"},
                    "course_type": {"type": "keyword"},
                    "prep_time_minutes": {"type": "integer"},
                    "cook_time_minutes": {"type": "integer"},
                    "servings": {"type": "integer"},
                    "ingredient_names": {"type": "text", "analyzer": "french_analyzer"},
                    "allergens": {"type": "keyword"},
                    "diets": {"type": "keyword"},
                    "nutrition": {"type": "keyword"},
                    "types": {"type": "keyword"},
                    "created_by_user_id": {"type": "keyword"},
                    "account_id": {"type": "keyword"},
                    "source_recipe_id": {"type": "integer"},
                    "created_at": {"type": "date"},
                    **MACRO_PROPERTIES,
                }
            },
        )
    else:
        # Ajout idempotent des champs sur un index pré-existant (macros + provenance
        # coaching). put_mapping n'écrase pas les champs déjà présents.
        await es_client.indices.put_mapping(
            index=index_name,
            properties={**MACRO_PROPERTIES, "source_recipe_id": {"type": "integer"}},
        )


async def close_elasticsearch():
    if es_client is not None:
        await es_client.close()
