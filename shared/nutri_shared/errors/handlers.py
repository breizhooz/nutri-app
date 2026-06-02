import logging
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import AppException

logger = logging.getLogger(__name__)

_I18N_KEY = re.compile(r"i18n:([\w.]+)")


def _localize_validation_errors(request: Request, exc: RequestValidationError) -> list:
    """Translate any ``i18n:<key>`` markers carried by validation messages.

    Validators may raise ``ValueError("i18n:some.key")``; the message is
    resolved here using the per-app translator (``app.state.translate``) and
    the request locale set by ``LocaleMiddleware``. Falls back to the raw
    message when no marker, translator, or locale is available.
    """
    locale = getattr(getattr(request, "state", None), "locale", "fr")
    translate = getattr(getattr(request.app, "state", None), "translate", None)
    errors = exc.errors()
    if translate is None:
        return errors
    for err in errors:
        msg = err.get("msg")
        if not isinstance(msg, str):
            continue
        match = _I18N_KEY.search(msg)
        if match:
            err["msg"] = translate(match.group(1), locale=locale)
    return errors


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.detail}},
        )

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _localize_validation_errors(request, exc)
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": str(errors)}},
        )

    @app.exception_handler(Exception)
    async def _generic_exc(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Internal server error",
                }
            },
        )
