from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import get_engine
from app.api.routes import sources as sources_routes
from app.api.routes import results as results_routes
from app.api.routes import settings as settings_routes

app = FastAPI(title="service-crawler", version="0.1.0")

app.include_router(sources_routes.router, prefix="/api/v1/crawler/sources", tags=["sources"])
app.include_router(results_routes.router, prefix="/api/v1/crawler/results", tags=["results"])
app.include_router(settings_routes.router, prefix="/api/v1/crawler/settings", tags=["settings"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-crawler"}


@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "service": "service-crawler", "database": db_status}