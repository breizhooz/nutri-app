from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class LocaleMiddleware(BaseHTTPMiddleware):
    SUPPORTED_LOCALES = {"fr", "en", "es"}
    DEFAULT_LOCALE = "fr"

    async def dispatch(self, request: Request, call_next):
        # Détecter la langue depuis le header Accept-Language
        accept_language = request.headers.get("Accept-Language", self.DEFAULT_LOCALE)

        # Extraire le premier code langue (avant la virgule)
        # Ex: "en-US,en;q=0.9,fr;q=0.8" -> "en-US" -> "en"
        locale = accept_language.split(",")[0].split("-")[0][:2].lower()

        # Vérifier que la locale est supportée
        if locale not in self.SUPPORTED_LOCALES:
            locale = self.DEFAULT_LOCALE

        # Stocker dans request.state pour y accéder dans les routes
        request.state.locale = locale

        response = await call_next(request)
        return response