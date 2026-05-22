from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from nutri_shared.errors import register_error_handlers

from app.db.session import get_engine
from app.i18n.middleware import LocaleMiddleware
from app.api.routes import shopping_list as shopping_list_router
from app.api.routes import weekly_menu as weekly_menu_router

from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await get_engine().dispose()


configure_logging("service-menu")
app = FastAPI(title="service-menu", version="0.1.0", lifespan=lifespan)
app.add_middleware(LocaleMiddleware)
app.add_middleware(RequestLoggingMiddleware)

register_error_handlers(app)

app.include_router(weekly_menu_router.router, prefix="/api/v1/menus", tags=["menus"])
app.include_router(
    shopping_list_router.router, prefix="/api/v1/menus", tags=["shopping-list"]
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-menu"}


@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "service": "service-menu", "database": db_status}
