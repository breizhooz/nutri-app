from fastapi import HTTPException, Request

from app.i18n.loader import t


class LocalizedHTTPException(HTTPException):
    def __init__(self, status_code: int, translation_key: str, request: Request, message: str | None = None, **kwargs):
        locale = getattr(request.state, "locale", "fr")
        base = t.get(translation_key, locale=locale, **kwargs)
        detail = f"{base} : {message}" if message is not None else base
        super().__init__(status_code=status_code, detail=detail)

    @staticmethod
    def subscription_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "subscription.errors.not_found", request)

    @staticmethod
    def subscription_already_exists(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(409, "subscription.errors.already_exists", request)

    @staticmethod
    def notification_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "notification.errors.not_found", request)

    @staticmethod
    def unauthorized(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(403, "common.errors.unauthorized", request)

    @staticmethod
    def dispatch_failed(request: Request, e: Exception) -> "LocalizedHTTPException":
        return LocalizedHTTPException(500, "notification.errors.dispatch_failed", request, message=str(e))
