from fastapi import Request
from nutri_shared.errors import AppException

from app.i18n.loader import t


class LocalizedHTTPException(AppException):
    def __init__(
        self,
        status_code: int,
        translation_key: str,
        request: Request,
        code: str = "UNKNOWN",
        message: str | None = None,
        **kwargs,
    ):
        locale = getattr(request.state, "locale", "fr")
        base = t.get(translation_key, locale=locale, **kwargs)
        full_message = f"{base} : {message}" if message is not None else base
        super().__init__(status_code=status_code, code=code, message=full_message)

    @staticmethod
    def menu_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "menu.errors.not_found", request, code="MENU_NOT_FOUND")

    @staticmethod
    def menu_unauthorized(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(403, "menu.errors.unauthorized", request, code="MENU_UNAUTHORIZED")

    @staticmethod
    def service_recipe_unavailable(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(503, "http_client.recipe.errors.unavailable", request, code="SERVICE_RECIPE_UNAVAILABLE")

    @staticmethod
    def service_failed(request: Request, translation_key: str, e: Exception) -> "LocalizedHTTPException":
        return LocalizedHTTPException(500, translation_key, request, code="SERVICE_ERROR", message=str(e))