from fastapi import HTTPException, Request
from app.i18n.loader import t


class LocalizedHTTPException(HTTPException):

    def __init__(self, status_code: int, translation_key: str, request: Request, message: str | None = None, **kwargs):
        locale = getattr(request.state, "locale", "fr")
        base = t.get(translation_key, locale=locale, **kwargs)
        detail = f"{base} : {message}" if message is not None else base
        super().__init__(status_code=status_code, detail=detail)

    @staticmethod
    def menu_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "menu.errors.not_found", request)

    @staticmethod
    def menu_unauthorized(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(403, "menu.errors.unauthorized", request)

    @staticmethod
    def service_recipe_unavailable(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(503, "http_client.recipe.errors.unavailable", request)

    @staticmethod
    def service_failed(request: Request, translation_key: str, e: Exception) -> "LocalizedHTTPException":
        return LocalizedHTTPException(500, translation_key=translation_key, message=str(e), request=request)