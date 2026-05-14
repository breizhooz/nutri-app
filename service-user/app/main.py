from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import get_engine
from app.api.routes import users as users_routes
from app.api.routes import auth as auth_routes


app = FastAPI(title="service-user", version="0.1.0")

app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_routes.router, prefix="/api/v1/users", tags=["users"])
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "service-user",
    }

@app.get("/health/db")
async def health_db():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "service": "service-user",
        "database": db_status,
    }