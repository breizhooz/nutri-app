"""FastAPI application entry point for service-user."""

from fastapi import FastAPI
from sqlalchemy import text

from nutri_shared.errors import register_error_handlers
from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware

from app.api.routes import auth as auth_routes
from app.api.routes import users as users_routes
from app.api.routes import mfa as mfa_routes
from app.api.routes import oauth as oauth_routes
from app.db.session import get_engine

configure_logging("service-user")
app: FastAPI = FastAPI(title="service-user", version="0.2.0")

app.add_middleware(RequestLoggingMiddleware)
register_error_handlers(app)

app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_routes.router, prefix="/api/v1/users", tags=["users"])
app.include_router(mfa_routes.router, prefix="/api/v1/auth/2fa", tags=["2fa"])
app.include_router(
    oauth_routes.router, prefix="/api/v1/auth/oauth", tags=["oauth"]
)


@app.get("/health")
async def health() -> dict:
    """Return service liveness status."""
    return {"status": "ok", "service": "service-user"}


@app.get("/health/db")
async def health_db() -> dict:
    """Return service and database connectivity status."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
    return {"status": "ok", "service": "service-user", "database": db_status}