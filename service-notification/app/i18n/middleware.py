from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LocaleMiddleware(BaseHTTPMiddleware):
    SUPPORTED_LOCALES = {"fr", "en"}
    DEFAULT_LOCALE = "fr"

    async def dispatch(self, request: Request, call_next):
        accept_language = request.headers.get("Accept-Language", self.DEFAULT_LOCALE)
        locale = accept_language.split(",")[0].split("-")[0][:2].lower()

        if locale not in self.SUPPORTED_LOCALES:
            locale = self.DEFAULT_LOCALE

        request.state.locale = locale

        response = await call_next(request)
        return response
