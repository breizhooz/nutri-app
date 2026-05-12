import os
import sys
from unittest.mock import MagicMock

# Inject fake weasyprint BEFORE any app module is loaded.
# In Docker slim (Python 3.12), weasyprint's cffi bindings load libgobject
# at import time — the process crashes before monkeypatch can intervene.
_weasy_mock = MagicMock()
_weasy_mock.HTML.return_value.write_pdf.return_value = b"%PDF-1.4 mock"
sys.modules["weasyprint"] = _weasy_mock

# Must be set before any app module is imported
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SERVICE_USER_URL", "http://service-user-test:8000")
os.environ.setdefault("SERVICE_RECIPE_URL", "http://service-recipe-test:8000")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("JWT_ALGORITHM", "HS256")


def make_recipe(
    id: int,
    allergens: list[str] | None = None,
    cals_per_100g: float | None = None,
    qty: float = 100,
    servings: int = 1,
    slug: str | None = None,
) -> dict:
    tags = allergens or []
    ingredient: dict = {"id": id * 10, "name": f"ingredient_{id}", "tags": tags}
    if cals_per_100g is not None:
        ingredient["calories_per_100g"] = cals_per_100g
    return {
        "id": id,
        "slug": slug or f"recipe-{id}",
        "title": f"Recipe {id}",
        "servings": servings,
        "recipe_ingredients": [
            {
                "ingredient_id": id * 10,
                "ingredient": ingredient,
                "quantity": qty,
                "unit": "g",
            }
        ],
    }


SAMPLE_RECIPES: list[dict] = [make_recipe(i, cals_per_100g=100.0) for i in range(1, 25)]

RECIPE_WITH_GLUTEN = make_recipe(50, allergens=["enums.allergen.gluten"], cals_per_100g=300.0)
RECIPE_WITH_EGGS   = make_recipe(51, allergens=["enums.allergen.eggs"],   cals_per_100g=200.0)

RICH_RECIPE = {
    "id": 100,
    "slug": "rich-recipe",
    "title": "Rich Recipe",
    "servings": 2,
    "recipe_ingredients": [
        {
            "ingredient_id": 1001,
            "ingredient": {
                "id": 1001,
                "name": "Pasta",
                "tags": ["enums.type.pasta"],
                "calories_per_100g": 350.0,
            },
            "quantity": 200,
            "unit": "g",
        },
        {
            "ingredient_id": 1002,
            "ingredient": {
                "id": 1002,
                "name": "Egg",
                "tags": [],
                "calories_per_100g": 155.0,
            },
            "quantity": 3,
            "unit": "unit",
        },
    ],
}


class MockRecipeClient:
    def __init__(self, recipes: list[dict] | None = None):
        self._recipes = recipes if recipes is not None else SAMPLE_RECIPES

    async def get_recipes(self, skip: int = 0, limit: int = 200) -> list[dict]:
        return self._recipes[skip : skip + limit]

    async def get_recipe_by_id(self, recipe_id: int) -> dict | None:
        return next((r for r in self._recipes if r["id"] == recipe_id), None)

    async def get_recipe_by_slug(self, slug: str) -> dict | None:
        return next((r for r in self._recipes if r.get("slug") == slug), None)