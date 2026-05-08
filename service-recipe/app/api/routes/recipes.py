from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.requests import Request
from app.db.session import get_session
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.schemas.recipe import RecipeCreate, RecipeResponse
from app.core.utils import slugify
from app.i18n import LocalizedHTTPException

router = APIRouter()

@router.post("/recipe", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe_data: RecipeCreate,
    session: AsyncSession = Depends(get_session)
):
    # Générer le slug à partir du titre
    slug = slugify(recipe_data.title)
    
    # Vérifier que le slug n'existe pas déjà
    existing = await session.execute(
        select(Recipe).where(Recipe.slug == slug)
    )
    if existing.scalar_one_or_none():
        # Ajouter un suffixe numérique si doublon
        counter = 1
        while True:
            new_slug = f"{slug}-{counter}"
            existing = await session.execute(
                select(Recipe).where(Recipe.slug == new_slug)
            )
            if not existing.scalar_one_or_none():
                slug = new_slug
                break
            counter += 1
    
    # Créer la recette
    recipe = Recipe(
        title=recipe_data.title,
        slug=slug,
        description=recipe_data.description,
        instructions=recipe_data.instructions,
        prep_time_minutes=recipe_data.prep_time_minutes,
        cook_time_minutes=recipe_data.cook_time_minutes,
        servings=recipe_data.servings,
        difficulty=recipe_data.difficulty,
        origin=recipe_data.origin_recipe,
        book_name=recipe_data.book_name,
        source_url=recipe_data.source_url,
        image_url=recipe_data.image_url
    )
    
    session.add(recipe)
    await session.flush()  # Obtenir recipe.id
    
    # Ajouter les ingrédients
    for ing_data in recipe_data.recipe_ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ing_data.ingredient_id,
            quantity=ing_data.quantity,
            unit=ing_data.unit
        )
        session.add(recipe_ingredient)
    
    await session.commit()
    await session.refresh(recipe)
    
    return recipe

@router.get("/{slug}", response_model=RecipeResponse)
async def get_recipe_by_slug(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """get recipe by slug"""
    result = await session.execute(
        select(Recipe).where(Recipe.slug == slug)
    )
    recipe = result.scalar_one_or_none()
    
    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    return recipe


@router.get("/id/{id}", response_model=RecipeResponse)
async def get_recipe_by_id(
    id: int,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """get recipe by id"""
    recipe = await session.get(Recipe, id)

    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)
    
    return recipe