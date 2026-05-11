from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.core.elasticsearch import init_elasticsearch, close_elasticsearch
from app.i18n.loader import t
from app.api.routes import recipes as recipes_router
from app.api.routes import ingredient as ingredient_router
from app.api.routes import search as search_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_elasticsearch()   # crée l'index si absent
    yield
    await close_elasticsearch()

app = FastAPI(title="service-recipe", version="0.1.0", lifespan=lifespan)

app.include_router(recipes_router.router, prefix="/api/v1/recipe", tags=["recipe"])
app.include_router(ingredient_router.router, prefix="/api/v1/ingredient", tags=["recipe"])
app.include_router(search_router.router,     prefix="/api/v1", tags=["search"])

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
