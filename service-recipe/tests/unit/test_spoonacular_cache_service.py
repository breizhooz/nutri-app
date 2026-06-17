import pytest

from app.core.exceptions import RecipeNotFound
from app.services.spoonacular_cache_service import SpoonacularCacheService
from app.services.spoonacular_service import SpoonacularRecipe


class _FakeClient:
    def __init__(self, recipes):
        self._recipes = recipes
        self.requested_count = None

    async def random_recipes(self, count):
        self.requested_count = count
        return self._recipes


class _Row:
    def __init__(self, spoonacular_id, payload):
        self.spoonacular_id = spoonacular_id
        self.payload = payload


class _FakeRepository:
    """Cache en mémoire : upsert renvoie True à la création, False sinon."""

    def __init__(self):
        self.store: dict[int, dict] = {}
        self.rows: dict[int, _Row] = {}

    async def upsert(self, *, spoonacular_id, title, image_url, source_url, payload):
        created = spoonacular_id not in self.store
        self.store[spoonacular_id] = {
            "title": title,
            "image_url": image_url,
            "source_url": source_url,
            "payload": payload,
        }
        return created

    async def get_by_spoonacular_id(self, spoonacular_id):
        return self.rows.get(spoonacular_id)

    async def get_random(self):
        return next(iter(self.rows.values()), None)


class _FakeRecipeService:
    def __init__(self):
        self.calls = []

    async def create_full(self, item, user_id, account_id):
        self.calls.append((item, user_id, account_id))
        return f"recipe::{item.title}::{user_id}::{account_id}"


def _recipe(rid: int) -> SpoonacularRecipe:
    return SpoonacularRecipe(
        spoonacular_id=rid,
        title=f"Recette {rid}",
        image_url=f"http://img/{rid}",
        source_url=f"http://src/{rid}",
        payload={"id": rid},
    )


class TestFetchAndCache:
    async def test_caches_new_recipes(self):
        repo = _FakeRepository()
        client = _FakeClient([_recipe(1), _recipe(2)])
        service = SpoonacularCacheService(repo, client=client)

        report = await service.fetch_and_cache(2)

        assert report.fetched == 2
        assert report.created == 2
        assert report.updated == 0
        assert set(repo.store) == {1, 2}
        assert client.requested_count == 2

    async def test_counts_updates_for_existing_recipes(self):
        repo = _FakeRepository()
        repo.store[1] = {"title": "ancienne"}  # déjà en cache
        client = _FakeClient([_recipe(1), _recipe(3)])
        service = SpoonacularCacheService(repo, client=client)

        report = await service.fetch_and_cache(2)

        assert report.fetched == 2
        assert report.created == 1  # seule la 3 est nouvelle
        assert report.updated == 1  # la 1 est mise à jour
        assert repo.store[1]["title"] == "Recette 1"

    async def test_empty_fetch_yields_zero_report(self):
        repo = _FakeRepository()
        client = _FakeClient([])
        service = SpoonacularCacheService(repo, client=client)

        report = await service.fetch_and_cache(3)

        assert (report.fetched, report.created, report.updated) == (0, 0, 0)
        assert repo.store == {}

    async def test_translates_payload_before_caching(self):
        from app.services.recipe_translator import RecipeTranslator

        repo = _FakeRepository()
        recipe = SpoonacularRecipe(
            spoonacular_id=1,
            title="Garlic Bread",
            image_url=None,
            source_url=None,
            payload={"id": 1, "title": "Garlic Bread"},
        )
        translator = RecipeTranslator(
            enabled=True, translate_batch=lambda texts: [t.upper() for t in texts]
        )
        service = SpoonacularCacheService(
            repo, client=_FakeClient([recipe]), translator=translator
        )

        await service.fetch_and_cache(1)

        # Le titre stocké et le payload sont la version traduite (ici majuscules).
        assert repo.store[1]["title"] == "GARLIC BREAD"
        assert repo.store[1]["payload"]["title"] == "GARLIC BREAD"


class TestGetRandom:
    async def test_returns_a_cached_row(self):
        repo = _FakeRepository()
        repo.rows[5] = _Row(5, {"id": 5, "title": "Plat"})
        service = SpoonacularCacheService(repo, client=_FakeClient([]))

        row = await service.get_random()
        assert row.spoonacular_id == 5

    async def test_raises_when_cache_empty(self):
        service = SpoonacularCacheService(_FakeRepository(), client=_FakeClient([]))
        with pytest.raises(RecipeNotFound):
            await service.get_random()


class TestAddToPersonalList:
    async def test_maps_and_calls_create_full(self):
        repo = _FakeRepository()
        repo.rows[7] = _Row(7, {"id": 7, "title": "Tarte", "servings": 6})
        service = SpoonacularCacheService(repo, client=_FakeClient([]))
        recipe_service = _FakeRecipeService()

        result = await service.add_to_personal_list(
            7, "user-1", "acc-1", recipe_service
        )

        assert result == "recipe::Tarte::user-1::acc-1"
        assert len(recipe_service.calls) == 1
        item, user_id, account_id = recipe_service.calls[0]
        assert item.title == "Tarte"
        assert item.servings == 6
        assert user_id == "user-1"
        assert account_id == "acc-1"

    async def test_raises_when_not_in_cache(self):
        service = SpoonacularCacheService(_FakeRepository(), client=_FakeClient([]))
        with pytest.raises(RecipeNotFound):
            await service.add_to_personal_list(
                999, "user-1", "acc-1", _FakeRecipeService()
            )
