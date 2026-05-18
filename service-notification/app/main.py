from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import history, notify, subscriptions
from app.db.session import get_engine
from app.i18n.middleware import LocaleMiddleware

app = FastAPI(title="service-notification", version="0.1.0")

app.add_middleware(LocaleMiddleware)

app.include_router(
    subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"],
    
)
app.include_router(notify.router, prefix="/api/v1/notify", tags=["notify"])
app.include_router(history.router, prefix="/api/v1/users", tags=["history"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "service-notification"}


@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
    return {"status": "ok", "service": "service-notification", "database": db_status}