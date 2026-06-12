import random
from datetime import date
from app.models.enums import DayOfWeek, MealType
from app.core.http_client import ServicesRecipeClient
from app.schemas.menu_slot import MenuSlotCreate
from app.services.profile_constraints import ProfileConstraints

_DAY_ORDER = list(DayOfWeek)
_DEFAULT_MEALS = [
    MealType.BREAKFAST,
    MealType.MORNING_SNACK,
    MealType.LUNCH,
    MealType.AFTERNOON_SNACK,
    MealType.DINNER,
]

# course_type values compatible avec chaque créneau de repas
_MEAL_COURSE_MAP: dict[MealType, set[str]] = {
    MealType.BREAKFAST: {
        "enums.course_type.breakfast",
        "enums.course_type.drink",
        "enums.course_type.snack",
    },
    MealType.MORNING_SNACK: {
        "enums.course_type.snack",
        "enums.course_type.drink",
        "enums.course_type.dessert",
        "enums.course_type.breakfast",
    },
    MealType.LUNCH: {
        "enums.course_type.starter",
        "enums.course_type.main",
        "enums.course_type.soup",
        "enums.course_type.salad",
        "enums.course_type.side_dish",
    },
    MealType.AFTERNOON_SNACK: {
        "enums.course_type.snack",
        "enums.course_type.drink",
        "enums.course_type.dessert",
        "enums.course_type.breakfast",
    },
    MealType.DINNER: {
        "enums.course_type.starter",
        "enums.course_type.main",
        "enums.course_type.soup",
        "enums.course_type.salad",
        "enums.course_type.side_dish",
    },
}


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


def _has_excluded_ingredient_name(
    recipe: dict, constraints: ProfileConstraints | None
) -> bool:
    """Vrai si un ingrédient de la recette porte un nom d'aliment exclu du profil."""
    if constraints is None or not constraints.excluded_food_terms:
        return False
    for ri in recipe.get("recipe_ingredients", []):
        name = (ri.get("ingredient") or {}).get("name") or ""
        if constraints.matches_excluded_name(name):
            return True
    return False


def _pool_for_meal(
    available: list[dict],
    meal_type: MealType,
    needed: int,
) -> list[dict]:
    """Retourne un pool suffisant pour `needed` créneaux du même type de repas.

    Filtre d'abord par course_type compatible ; si le résultat est trop petit,
    complète avec toutes les recettes disponibles (fallback gracieux).
    """
    allowed = _MEAL_COURSE_MAP.get(meal_type)
    if allowed:
        filtered = [r for r in available if r.get("course_type") in allowed]
    else:
        filtered = available.copy()

    # Fallback : si aucune recette ne correspond au type, on prend tout
    if not filtered:
        filtered = available.copy()

    random.shuffle(filtered)
    pool = filtered.copy()
    while len(pool) < needed:
        extra = filtered.copy()
        random.shuffle(extra)
        pool.extend(extra)
    return pool


async def generate_slots(
    recipe_client: ServicesRecipeClient,
    nb_persons: int,
    start_date: date,
    exclusions: list,
    caloric_target: int | None = None,
    meal_types: list[MealType] | None = None,
    duration_days: int = 7,
    constraints: ProfileConstraints | None = None,
) -> list[MenuSlotCreate]:
    if meal_types is None:
        meal_types = _DEFAULT_MEALS

    # Exclusions par tags : celles du payload ∪ celles du profil (allergies
    # déclarées + régime alimentaire). Les exclusions par nom d'aliment du
    # profil sont appliquées en plus, ingrédient par ingrédient.
    exclusion_values = {e.value if hasattr(e, "value") else e for e in exclusions}
    if constraints is not None:
        exclusion_values |= constraints.excluded_tags
        if caloric_target is None:
            caloric_target = constraints.target_calories

    recipes = await recipe_client.get_recipes(max_recipes=200)
    available = [
        r
        for r in recipes
        if not _has_excluded_allergen(r, exclusion_values)
        and not _has_excluded_ingredient_name(r, constraints)
    ]

    if not available:
        raise ValueError("Aucune recette disponible après application des exclusions.")

    # Soft caloric constraint par créneau (budget = cible / nb créneaux principaux)
    if caloric_target:
        main_meals = {MealType.LUNCH, MealType.DINNER}
        active_main = [m for m in meal_types if m in main_meals] or meal_types
        budget = caloric_target / len(active_main)
        fitting = [
            r
            for r in available
            if (c := _calories_per_serving(r)) is None or c <= budget
        ]
        if len(fitting) >= duration_days * len(meal_types):
            available = fitting

    slots = []
    for meal_type in meal_types:
        pool = _pool_for_meal(available, meal_type, duration_days)
        for i, day in enumerate(_DAY_ORDER[:duration_days]):
            slots.append(
                MenuSlotCreate(
                    day_of_week=day,
                    meal_type=meal_type,
                    recipe_id=pool[i]["id"],
                    nb_persons=nb_persons,
                )
            )

    # Trier par jour puis par repas pour un retour cohérent
    meal_order = {m: idx for idx, m in enumerate(meal_types)}
    day_order = {d: idx for idx, d in enumerate(_DAY_ORDER[:duration_days])}
    slots.sort(key=lambda s: (day_order[s.day_of_week], meal_order[s.meal_type]))

    return slots
