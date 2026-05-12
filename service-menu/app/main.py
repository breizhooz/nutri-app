from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.i18n.middleware import LocaleMiddleware
from app.api.routes import shopping_list as shopping_list_router
from app.api.routes import weekly_menu as weekly_menu_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(title="service-menu", version="0.1.0", lifespan=lifespan)

app.add_middleware(LocaleMiddleware)
app.include_router(weekly_menu_router.router, prefix="/api/v1/menus", tags=["menus"])
app.include_router(shopping_list_router.router, prefix="/api/v1/menus", tags=["shopping-list"])
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
