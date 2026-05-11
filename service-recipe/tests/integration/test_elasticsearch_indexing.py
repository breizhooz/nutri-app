import pytest
from unittest.mock import AsyncMock, MagicMock
from .conftest import make_mock_recipe

BASE = "/api/v1/recipe"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_recipe_triggers_es_indexation(override_db, override_user_client, mock_es, http_client):
    """Après une création, es_client.index() doit être appelé une fois."""
    mock_recipe = make_mock_recipe()

    async def mock_refresh(obj):
        obj.id = mock_recipe.id
        obj.created_at = mock_recipe.created_at
        obj.updated_at = mock_recipe.updated_at
        obj.recipe_ingredients = []
        obj.cuisine_origin = mock_recipe.cuisine_origin
        obj.course_type = mock_recipe.course_type
        obj.tags = {}
    override_db.refresh.side_effect = mock_refresh

    async with http_client as client:
        response = await client.post(BASE, json={
            "title": "Poulet rôti",
            "instructions": "Cuire au four 1h.",
            "recipe_ingredients": [],
            "created_by_user_id": "123e4567-e89b-12d3-a456-426614174000",
        })

    assert response.status_code == 201
    mock_es.index.assert_called_once()
    assert mock_es.index.call_args.kwargs["index"] == "recipes"
    assert mock_es.index.call_args.kwargs["id"] == mock_recipe.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_recipe_es_failure_does_not_break_crud(override_db, override_user_client, mock_es, http_client):
    """Si ES est down, la création en DB doit quand même réussir."""
    mock_es.index.side_effect = Exception("ES connection refused")

    async def mock_refresh(obj):
        from datetime import datetime
        from app.models.enums import CuisineOrigin, CourseType
        obj.id = 1
        obj.created_at = datetime(2026, 1, 1, 12, 0, 0)
        obj.updated_at = datetime(2026, 1, 1, 12, 0, 0)
        obj.recipe_ingredients = []
        obj.cuisine_origin = CuisineOrigin.FRENCH
        obj.course_type = CourseType.MAIN_COURSE
        obj.tags = {}
    override_db.refresh.side_effect = mock_refresh

    async with http_client as client:
        response = await client.post(BASE, json={
            "title": "Poulet rôti",
            "instructions": "Cuire au four 1h.",
            "recipe_ingredients": [],
        })

    assert response.status_code == 201


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_recipe_triggers_es_reindexation(override_db, mock_es, http_client):
    mock_recipe = make_mock_recipe()
    override_db.get.return_value = mock_recipe

    async with http_client as client:
        response = await client.put(f"{BASE}/id/{mock_recipe.id}", json={"title": "Poulet revisité"})

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
async def test_delete_recipe_triggers_es_deletion(override_db, mock_es, http_client):
    mock_recipe = make_mock_recipe()
    override_db.get.return_value = mock_recipe

    async with http_client as client:
        response = await client.delete(f"{BASE}/id/{mock_recipe.id}")

    assert response.status_code == 204
    mock_es.delete.assert_called_once_with(index="recipes", id=mock_recipe.id)


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
async def test_indexed_document_contains_allergens_from_ingredients(mock_es):
    """_build_document extrait les allergens depuis ingredient.tags."""
    from app.services.search_service import search_service
    from app.models.enums import Allergen

    gluten = Allergen.GLUTEN.value
    milk = Allergen.MILK.value

    ing1 = MagicMock(); ing1.name = "farine"; ing1.tags = [gluten, "enums.type.cereals"]
    ing2 = MagicMock(); ing2.name = "beurre"; ing2.tags = [milk]
    ri1 = MagicMock(); ri1.ingredient = ing1
    ri2 = MagicMock(); ri2.ingredient = ing2

    recipe = make_mock_recipe(recipe_ingredients=[ri1, ri2])
    doc = search_service._build_document(recipe)

    assert set(doc["allergens"]) == {gluten, milk}
    assert "farine" in doc["ingredient_names"]
    assert "beurre" in doc["ingredient_names"]