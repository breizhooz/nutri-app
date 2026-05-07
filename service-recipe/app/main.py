from fastapi import FastAPI, Request, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.db.session import get_session
from app.i18n.loader import t
from app.api.routes import recipes as recipes_router


app = FastAPI(title="service-recipe", version="0.1.0")

app.include_router(recipes_router.router, prefix="/api/v1/recipe", tags=["recipe"])

# app.include_router(users_routes.router, prefix="/api/v1/users", tags=["users"])
@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "service-recipe",
        "database": db_status,
    }

@app.get("/recipes/{id}")
async def get_recipe(id: int, request: Request,db: AsyncSession = Depends(get_session)):
    recipe = await db.get(id)
    locale = request.state.locale  # fr, en, es...
    
    return {
        "title": recipe.title,
        "difficulty": t.get(recipe.difficulty.value, locale=locale),  # "Facile"
        "cuisine": t.get(recipe.cuisine_origin.value, locale=locale)  # "française"
    }