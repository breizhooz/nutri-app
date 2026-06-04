from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from nutri_shared.errors import register_error_handlers

from app.core.error_handlers import register_domain_handlers
from app.db.session import get_engine
from app.i18n.loader import t
from app.i18n.middleware import LocaleMiddleware
from app.core.elasticsearch import init_elasticsearch, close_elasticsearch
from app.api.routes import recipes as recipes_router
from app.api.routes import ingredient as ingredient_router
from app.api.routes import search as search_router
from app.api.routes import spoonacular as spoonacular_router

from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.telemetry import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_elasticsearch()
    yield
    await close_elasticsearch()


configure_logging("service-recipe")
app = FastAPI(title="service-recipe", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(LocaleMiddleware)
app.state.translate = t.get

register_error_handlers(app)
register_domain_handlers(app)
setup_telemetry("service-recipe", app)

app.include_router(recipes_router.router, prefix="/api/v1/recipe", tags=["recipe"])
app.include_router(
    spoonacular_router.router,
    prefix="/api/v1/recipe/spoonacular",
    tags=["recipe"],
)
app.include_router(
    ingredient_router.router, prefix="/api/v1/ingredient", tags=["recipe"]
)
app.include_router(search_router.router, prefix="/api/v1", tags=["search"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-recipe"}


@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "service": "service-recipe", "database": db_status}
