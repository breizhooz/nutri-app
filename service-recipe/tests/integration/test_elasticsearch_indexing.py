import pytest
from unittest.mock import AsyncMock, MagicMock
from .conftest import make_mock_recipe

from app.api.routes.recipes import RecipeServiceFactory
from app.main import app
from app.services.recipe_service import RecipeService
from app.services.search_service import search_service
from app.services.unsplash_service import UnsplashService

BASE = "/api/v1/recipe"


def _override_service_with_real_search(recipe) -> RecipeService:
    """RecipeService réel (donc vrai search_service → ES patché) câblé sur un
    repository mocké. Unsplash désactivé (pas d'appel réseau)."""
    repo = AsyncMock()
    repo.slug_exists.return_value = False
    repo.create.return_value = recipe
    repo.get_by_id_with_relations.return_value = recipe
    repo.apply_update.return_value = recipe
    repo.update_image_suggestions.return_value = recipe
    service = RecipeService(
        repo,
        search_service,
        nutrition_client=AsyncMock(),
        unsplash=UnsplashService(access_key=""),
    )
    app.dependency_overrides[RecipeServiceFactory.inject] = lambda: service
    return service


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_recipe_triggers_es_indexation(
    override_user_client, mock_es, http_client
):
    """Après une création, es_client.index() doit être appelé une fois."""
    mock_recipe = make_mock_recipe()
    _override_service_with_real_search(mock_recipe)

    async with http_client as client:
        response = await client.post(
            BASE,
            json={
                "title": "Poulet rôti",
                "instructions": "Cuire au four 1h.",
                "recipe_ingredients": [],
            },
        )

    app.dependency_overrides.pop(RecipeServiceFactory.inject, None)

    assert response.status_code == 201
    mock_es.index.assert_called_once()
    from app.core.config import settings

    assert (
        mock_es.index.call_args.kwargs["index"] == settings.ELASTICSEARCH_INDEX_RECIPES
    )
    assert mock_es.index.call_args.kwargs["id"] == mock_recipe.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_recipe_es_failure_does_not_break_crud(
    override_user_client, mock_es, http_client
):
    """Si ES est down, la création en DB doit quand même réussir."""
    mock_es.index.side_effect = Exception("ES connection refused")
    _override_service_with_real_search(make_mock_recipe())

    async with http_client as client:
        response = await client.post(
            BASE,
            json={
                "title": "Poulet rôti",
                "instructions": "Cuire au four 1h.",
                "recipe_ingredients": [],
            },
        )

    app.dependency_overrides.pop(RecipeServiceFactory.inject, None)

    assert response.status_code == 201


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_recipe_triggers_es_reindexation(mock_es, http_client):
    mock_recipe = make_mock_recipe()
    _override_service_with_real_search(mock_recipe)

    async with http_client as client:
        response = await client.put(
            f"{BASE}/id/{mock_recipe.id}", json={"title": "Poulet revisité"}
        )

    app.dependency_overrides.pop(RecipeServiceFactory.inject, None)

    assert response.status_code == 200
    mock_es.index.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_nonexistent_recipe_returns_404(override_db, mock_es, http_client):
    override_db.get.return_value = None

    async with http_client as client:
        response = await client.put(f"{BASE}/id/9999", json={"title": "X"})

    assert response.status_code == 404
    mock_es.index.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_recipe_triggers_es_deletion(mock_es, http_client):
    mock_recipe = make_mock_recipe()
    _override_service_with_real_search(mock_recipe)

    async with http_client as client:
        response = await client.delete(f"{BASE}/id/{mock_recipe.id}")

    app.dependency_overrides.pop(RecipeServiceFactory.inject, None)

    assert response.status_code == 204
    from app.core.config import settings

    mock_es.delete.assert_called_once_with(
        index=settings.ELASTICSEARCH_INDEX_RECIPES, id=mock_recipe.id
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_nonexistent_recipe_returns_404(override_db, mock_es, http_client):
    override_db.get.return_value = None

    async with http_client as client:
        response = await client.delete(f"{BASE}/id/9999")

    assert response.status_code == 404
    mock_es.delete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_indexed_document_contains_user_id(mock_es):
    """Le document indexé dans ES doit contenir created_by_user_id issu du JWT."""
    from app.services.search_service import search_service
    from .conftest import TEST_USER_ID

    recipe = make_mock_recipe()
    doc = search_service._build_document(recipe)

    assert doc["created_by_user_id"] == TEST_USER_ID


@pytest.mark.asyncio
@pytest.mark.integration
async def test_indexed_document_contains_macros(mock_es):
    """_build_document projette les macros par portion sur les noms du moteur (fr)."""
    from app.services.search_service import search_service

    recipe = make_mock_recipe()
    doc = search_service._build_document(recipe)

    assert doc["calories"] == 520.0
    assert doc["proteines"] == 42.0  # proteins_per_serving
    assert doc["glucides"] == 30.0  # carbs_per_serving
    assert doc["lipides"] == 18.0  # fats_per_serving


@pytest.mark.asyncio
@pytest.mark.integration
async def test_indexed_document_contains_allergens_from_ingredients(mock_es):
    """_build_document extrait les allergens depuis ingredient.tags."""
    from app.services.search_service import search_service
    from app.models.enums import Allergen

    gluten = Allergen.GLUTEN.value
    milk = Allergen.MILK.value

    ing1 = MagicMock()
    ing1.name = "farine"
    ing1.tags = [gluten, "enums.type.cereals"]
    ing2 = MagicMock()
    ing2.name = "beurre"
    ing2.tags = [milk]
    ri1 = MagicMock()
    ri1.ingredient = ing1
    ri2 = MagicMock()
    ri2.ingredient = ing2

    recipe = make_mock_recipe(recipe_ingredients=[ri1, ri2])
    doc = search_service._build_document(recipe)

    assert set(doc["allergens"]) == {gluten, milk}
    assert "farine" in doc["ingredient_names"]
    assert "beurre" in doc["ingredient_names"]
