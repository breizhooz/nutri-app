from collections import defaultdict
from app.models.weekly_menu import WeeklyMenu
from app.core.http_client import ServicesRecipeClient
from app.schemas.shopping_list import ShoppingList, ShoppingItem

async def build_shopping_list(
        menu: WeeklyMenu,
        recipe_client: ServicesRecipeClient,
) -> ShoppingList:
    aggregated: dict[int, dict] = defaultdict(
        lambda: {"name": "", "unit": "", "category": None, "total_quantity": 0.0}
    )

    for slot in menu.slots:
        recipe = await recipe_client.get_recipe_by_id(slot.recipe_id)
        if not recipe:
            continue
        for ri in recipe.get("recipe_ingredients", []):
            ingredient = ri.get("ingredient") or {}
            ing_id = ri.get("ingredient_id") or ingredient.get("id")
            if not ing_id:
                continue
            agg = aggregated[ing_id]
            agg["total_quantity"] += (ri.get("quantity") or 0) * menu.nb_persons
            agg["name"] = ingredient.get("name", f"ingredient_{ing_id}")
            agg["unit"] = ri.get("unit", "")
            if not agg["category"]:
                tags = ingredient.get("tags") or []
                agg["category"] = tags[0] if tags else None

    items = [
        ShoppingItem(
            ingredient_id=ing_id,
            ingredient_name=data["name"],
            total_quantity=round(data["total_quantity"], 2),
            unit=data["unit"],
            category=data["category"],
        )
        for ing_id, data in aggregated.items()
    ]
    items.sort(key=lambda x: (x.category or "", x.ingredient_name))

    return ShoppingList(
        menu_id=menu.id,
        menu_slug=menu.slug or "",
        nb_persons=menu.nb_persons,
        start_date=menu.start_date,
        items=items,
    )