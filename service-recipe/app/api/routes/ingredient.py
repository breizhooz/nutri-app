from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session  # À adapter selon ton import de session
from app.models.ingredient import Ingredient
from app.schemas.ingredient import IngredientCreate, IngredientUpdate, IngredientResponse

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

@router.post("/", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    obj_in: IngredientCreate, 
    session: AsyncSession = Depends(get_session)):

    # Vérification si le nom existe déjà (unique=True dans le modèle)
    existing = session.execute(select(Ingredient).where(Ingredient.name == obj_in.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Cet ingrédient existe déjà.")
    
    # Conversion du schéma en dictionnaire pour créer l'objet
    # Pydantic gérera la conversion des Enums en strings automatiquement
    db_obj = Ingredient(**obj_in.model_dump())
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj

@router.get("/", response_model=List[IngredientResponse])
def read_ingredients(
    skip: int = 0, 
    limit: int = 100, 
    session: AsyncSession = Depends(get_session)):
    query = select(Ingredient).offset(skip).limit(limit)
    ingredients = session.execute(query).scalars().all()
    return ingredients

@router.get("/{ingredient_id}", response_model=IngredientResponse)
def read_ingredient(ingredient_id: int, session: AsyncSession = Depends(get_session)):
    db_obj = session.get(Ingredient, ingredient_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Ingrédient non trouvé")
    return db_obj

@router.patch("/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(ingredient_id: int, obj_in: IngredientUpdate, session: AsyncSession = Depends(get_session)):
    db_obj = session.get(Ingredient, ingredient_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Ingrédient non trouvé")
    
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    session.commit()
    session.refresh(db_obj)
    return db_obj

@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(ingredient_id: int, session: AsyncSession = Depends(get_session)):
    db_obj = session.get(Ingredient, ingredient_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Ingrédient non trouvé")
    
    session.delete(db_obj)
    session.commit()
    return None