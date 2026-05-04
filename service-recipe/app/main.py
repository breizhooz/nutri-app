from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import engine


app = FastAPI(title="service-recipe", version="0.1.0")

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
        "service": "service-user",
        "database": db_status,
    }