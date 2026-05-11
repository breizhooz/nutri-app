from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from elasticsearch import NotFoundError

from app.core.http_client import ServicesUserClient, get_user_client, ServiceUnavailableError
from app.db.session import get_session
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.schemas.recipe import RecipeCreate, RecipeResponse, RecipeUpdate
from app.core.utils import slugify
from app.i18n import LocalizedHTTPException
from app.i18n.loader import t
from app.services.search_service import search_service
from app.core.deps import get_current_user_id


router = APIRouter()

async def _load_with_relations(session: AsyncSession, recipe_id:int):
    """
    Load a recipe with ingredients (eager load required in async SQLAlchemy).
    """
    result = await session.execute(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient)
        )
    )

    return result.scalar_one_or_none()
    
@router.put("/id/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
     recipe_id: int,
     recipe_data: RecipeUpdate,
     request: Request,
     session: AsyncSession = Depends(get_session),
     current_user_id: str = Depends(get_current_user_id)
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)
    
    if recipe.created_by_user_id is None or str(recipe.created_by_user_id) != current_user_id:
        raise LocalizedHTTPException.unauthorized(request)

    update_fields = recipe_data.model_dump(exclude_unset=True, exclude={"recipe_ingredients"})

    #renew the slug if change title
    if "title" in update_fields:
        new_slug = slugify(update_fields["title"])
        conflict = await session.execute(
            select(Recipe).where(Recipe.slug == new_slug, Recipe.id != recipe_id)
        )
        if conflict.scalar_one_or_none():
            i = 1
            while True:
                if i > 100:
                    raise LocalizedHTTPException.slug_too_big(request)
                candidate = f"{new_slug} - {i}"
                conflict = await session.execute(
                    select(Recipe).where(Recipe.slug == candidate, Recipe.id != recipe_id)
                )
                if not conflict.scalar_one_or_none():
                    new_slug = candidate
                    break
                i +=1
        update_fields['slug'] = new_slug
    
    for field, value in update_fields.items():
        setattr(recipe, field, value)
    
    if recipe_data.recipe_ingredients is not None:
        await session.execute(
            delete(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
        )
        for ing_data in recipe_data.recipe_ingredients:
            session.add(RecipeIngredient(
                recipe_id=recipe_id,
                ingredient_id=ing_data.ingredient_id,
                quantity=ing_data.quantity,
                unit=ing_data.unit,
            ))

    await session.commit()

    recipe_with_relations = await _load_with_relations(session, recipe_id)
    recipe_to_return = recipe_with_relations if recipe_with_relations is not None else recipe

    try:
        await search_service.index_recipe(recipe_to_return)
    except Exception as e:
        locale = getattr(request.state, "locale", "fr")
        print(f"{t.get('elasticsearch.errors.update_indexation_for_recipe', locale=locale)} : {recipe_id} : {e}")


    return recipe_to_return
            

@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe_data: RecipeCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_client: ServicesUserClient = Depends(get_user_client),
    current_user_id: str = Depends(get_current_user_id)
):
    recipe_data.created_by_user_id = current_user_id
    try:
        exists = await user_client.user_exist(str(recipe_data.created_by_user_id))
    except ServiceUnavailableError:
        raise LocalizedHTTPException.service_user_unavailable(request)
    if not exists:
        raise LocalizedHTTPException.user_id_not_exists(request)
    

    # Générer le slug à partir du titre
    slug = slugify(recipe_data.title)
    
    # Vérifier que le slug n'existe pas déjà
    existing = await session.execute(
        select(Recipe).where(Recipe.slug == slug)
    )
    if existing.scalar_one_or_none():
        # Ajouter un suffixe numérique si doublon
        i = 1
        while True:
            if i > 100:
                    raise LocalizedHTTPException.slug_too_big(request)
            new_slug = f"{slug}-{i}"
            existing = await session.execute(
                select(Recipe).where(Recipe.slug == new_slug)
            )
            if not existing.scalar_one_or_none():
                slug = new_slug
                break
            i += 1
    
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
        cuisine_origin=recipe_data.cuisine_origin, 
        origin_recipe=recipe_data.origin_recipe,
        course_type=recipe_data.course_type, 
        tags=recipe_data.tags,
        book_name=recipe_data.book_name,
        source_url=recipe_data.source_url,
        image_url=recipe_data.image_url,
        created_by_user_id=current_user_id
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
    
    recipe_with_relations = await _load_with_relations(session, recipe.id)
    recipe_to_return = recipe_with_relations if recipe_with_relations is not None else recipe

    try:
        await search_service.index_recipe(recipe_to_return)
    except Exception as e:
        locale = getattr(request.state, "locale", "fr")
        print(f"{t.get('elasticsearch.errors.indexation_for_recipe', locale=locale)} : {e}")

    return recipe_to_return

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

@router.delete("/id/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(
    recipe_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user_id: str = Depends(get_current_user_id)
):
    recipe = await session.get(Recipe, recipe_id)
    if not recipe:
        raise LocalizedHTTPException.recipe_not_found(request)

    if recipe.created_by_user_id is None or str(recipe.created_by_user_id) != current_user_id: 
        raise LocalizedHTTPException.unauthorized(request)

    await session.delete(recipe)
    await session.commit()

    try:
        await search_service.delete_recipe(recipe_id)
    except NotFoundError:
        pass