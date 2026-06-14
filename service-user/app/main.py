"""FastAPI application entry point for service-user."""

from fastapi import FastAPI

from nutri_shared.errors import register_error_handlers
from nutri_shared.core.logger import configure_logging
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.telemetry import setup_telemetry

from app.api.routes import accounts as accounts_routes
from app.api.routes import auth as auth_routes
from app.api.routes import consents as consents_routes
from app.api.routes import users as users_routes
from app.api.routes import mfa as mfa_routes
from app.api.routes import oauth as oauth_routes
from app.api.routes import password as password_routes  # ← nouveau
from app.api.routes import health as health_routes
from app.i18n.loader import t
from app.i18n.middleware import LocaleMiddleware

configure_logging("service-user")
app: FastAPI = FastAPI(title="service-user", version="0.2.0")

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(LocaleMiddleware)
app.state.translate = t.get
register_error_handlers(app)
setup_telemetry("service-user", app)

app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_routes.router, prefix="/api/v1/users", tags=["users"])
app.include_router(consents_routes.router, prefix="/api/v1/users", tags=["consents"])
app.include_router(accounts_routes.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(mfa_routes.router, prefix="/api/v1/auth/2fa", tags=["2fa"])
app.include_router(oauth_routes.router, prefix="/api/v1/auth/oauth", tags=["oauth"])
app.include_router(
    password_routes.router, prefix="/api/v1/auth/password", tags=["password"]
)  # ← nouveau
app.include_router(health_routes.router, tags=["health"])
