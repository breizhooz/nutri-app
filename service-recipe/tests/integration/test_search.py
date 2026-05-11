import pytest

SEARCH_BASE = "/api/v1/search/recipes"


def _es_response(hits=None, total=0):
    return {"hits": {"total": {"value": total}, "hits": hits or []}}


def _es_hit(recipe_id, title, score=1.0, **extra):
    return {
        "_id": str(recipe_id), "_score": score,
        "_source": {
            "title": title, "slug": title.lower().replace(" ", "-"),
            "description": None, "difficulty": "enums.difficulty.easy",
            "cuisine_origin": "enums.cuisine.french", "origin_recipe": "enums.origin.personal",
            "course_type": "enums.course.main", "prep_time_minutes": 20,
            "cook_time_minutes": 30, "servings": 4, "ingredient_names": [],
            "allergens": [], "created_by_user_id": None,
            "created_at": "2026-01-01T12:00:00", **extra,
        },
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_returns_structured_response(mock_es, http_client):
    mock_es.search.return_value = _es_response(hits=[_es_hit(1, "Tarte aux pommes", score=1.8)], total=1)

    async with http_client as client:
        response = await client.get(SEARCH_BASE, params={"q": "tarte"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Tarte aux pommes"
    assert data["results"][0]["id"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_without_q_uses_match_all(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        await client.get(SEARCH_BASE)
    call_kwargs = mock_es.search.call_args.kwargs
    # body = mock_es.search.call_args.kwargs["body"]
    assert any("match_all" in c for c in call_kwargs["query"]["bool"]["must"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_with_q_uses_multi_match(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        await client.get(SEARCH_BASE, params={"q": "tarte"})
    call_kwargs = mock_es.search.call_args.kwargs
    must = call_kwargs["query"]["bool"]["must"]
    assert any("multi_match" in c for c in must)
    mm = next(c["multi_match"] for c in must if "multi_match" in c)
    assert mm["query"] == "tarte"
    assert "title^3" in mm["fields"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_difficulty_filter(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        await client.get(SEARCH_BASE, params={"difficulty": "enums.difficulty.easy"})
    filters = mock_es.search.call_args.kwargs["query"]["bool"]["filter"]
    assert {"term": {"difficulty": "enums.difficulty.easy"}} in filters


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_max_prep_time_filter(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        await client.get(SEARCH_BASE, params={"max_prep_time": 30})
    filters = mock_es.search.call_args.kwargs["query"]["bool"]["filter"]
    assert {"range": {"prep_time_minutes": {"lte": 30}}} in filters


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_exclude_allergens(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        await client.get(SEARCH_BASE, params=[
            ("exclude_allergens", "enums.allergen.gluten"),
            ("exclude_allergens", "enums.allergen.milk"),
        ])
    must_not = mock_es.search.call_args.kwargs["query"]["bool"]["must_not"]
    excluded = [c["term"]["allergens"] for c in must_not]
    assert "enums.allergen.gluten" in excluded
    assert "enums.allergen.milk" in excluded


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_pagination(mock_es, http_client):
    mock_es.search.return_value = _es_response()
    async with http_client as client:
        response = await client.get(SEARCH_BASE, params={"limit": 5, "offset": 20})
    body = mock_es.search.call_args.kwargs
    assert body["size"] == 5
    assert body["from"] == 20
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 20


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_limit_max_returns_422(mock_es, http_client):
    async with http_client as client:
        response = await client.get(SEARCH_BASE, params={"limit": 200})
    assert response.status_code == 422