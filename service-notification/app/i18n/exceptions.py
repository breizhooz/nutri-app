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
    def subscription_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "subscription.errors.not_found", request, code="SUBSCRIPTION_NOT_FOUND")

    @staticmethod
    def subscription_already_exists(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(409, "subscription.errors.already_exists", request, code="SUBSCRIPTION_ALREADY_EXISTS")

    @staticmethod
    def notification_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(404, "notification.errors.not_found", request, code="NOTIFICATION_NOT_FOUND")

    @staticmethod
    def unauthorized(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(403, "common.errors.unauthorized", request, code="UNAUTHORIZED")

    @staticmethod
    def dispatch_failed(request: Request, e: Exception) -> "LocalizedHTTPException":
        return LocalizedHTTPException(500, "notification.errors.dispatch_failed", request, code="NOTIFICATION_DISPATCH_FAILED", message=str(e))