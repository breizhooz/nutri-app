from typing import Optional

from pydantic import BaseModel


class HydratedIngredient(BaseModel):
    name: str
    quantity: float
    unit: str


class RecipeHydrated(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: str
    servings: int = 4
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    ingredients: list[HydratedIngredient]
    groq_tokens_used: int
    from_cache: bool = False
    is_recipe: bool = True
    recipe_confidence: float = 1.0


class RecipeCommitRequest(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: str
    servings: int = 4
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    ingredients: list[HydratedIngredient]
    course_type: Optional[str] = None
    free_tags: list[str] = []
