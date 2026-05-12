import random
from datetime import date
from app.models.enums import DayOfWeek, MealType
from app.core.http_client import ServicesRecipeClient
from app.schemas.menu_slot import MenuSlotCreate

_DAY_ORDER = list(DayOfWeek)
_DEFAULT_MEALS = [MealType.LUNCH, MealType.DINNER]

def _calories_per_serving(recipe: dict) -> float | None:
    total = 0.0
    ingredients = recipe.get("recipe_ingredients", [])
    if not ingredients:
        return None
    for ri in ingredients:
        cal = (ri.get("ingredient") or {}).get("calories_per_100g")
        qty = ri.get("quantity") or 0
        if cal is not None:
            total += (cal / 100) * qty
        
    servings = recipe.get("servings") or 1

    return total / servings

def _has_excluded_allergen(recipe: dict, exclusions: set[str]) -> bool:
    if not exclusions:
        return False
    for ri in recipe.get("recipe_ingredients", []):
        for tag in (ri.get("ingredient") or {}).get("tags", []):
            if tag in exclusions:
                return True
    return False

async def generate_slots(
    recipe_client: ServicesRecipeClient,
    nb_persons: int,
    start_date: date,
    exclusions: list,
    caloric_target: int | None = None,
    meal_types: list[MealType] | None = None,
    duration_days: int = 7,
) -> list[MenuSlotCreate]:
    if meal_types is None:
        meal_types = _DEFAULT_MEALS

    exclusion_values = {e.value if hasattr(e, "value") else e for e in exclusions}
    total_slots = duration_days * len(meal_types)

    recipes = await recipe_client.get_recipes(limit=200)
    available = [r for r in recipes if not _has_excluded_allergen(r, exclusion_values)]

    if not available:
        raise ValueError("Aucune recette disponible après application des exclusions.")

    # Soft caloric constraint : on filtre si on a assez de recettes
    if caloric_target and len(available) > total_slots:
        budget = caloric_target / len(meal_types)
        fitting = [r for r in available if (c := _calories_per_serving(r)) is None or c <= budget]
        if len(fitting) >= total_slots:
            available = fitting

    random.shuffle(available)

    # Si pas assez de recettes uniques, on autorise les répétitions entre semaines
    pool = available.copy()
    while len(pool) < total_slots:
        extra = available.copy()
        random.shuffle(extra)
        pool.extend(extra)

    slots = []
    for i, day in enumerate(_DAY_ORDER[:duration_days]):
        for j, meal_type in enumerate(meal_types):
            recipe = pool[i * len(meal_types) + j]
            slots.append(MenuSlotCreate(
                day_of_week=day,
                meal_type=meal_type,
                recipe_id=recipe["id"],
            ))

    return slots