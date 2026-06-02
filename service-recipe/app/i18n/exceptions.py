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
    def recipe_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            404, "recipe.errors.not_found", request, code="RECIPE_NOT_FOUND"
        )

    @staticmethod
    def unauthorized(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            403, "recipe.errors.unauthorized", request, code="RECIPE_UNAUTHORIZED"
        )

    @staticmethod
    def image_service_unavailable(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            503,
            "recipe.errors.image_service_unavailable",
            request,
            code="IMAGE_SERVICE_UNAVAILABLE",
        )

    @staticmethod
    def ingredient_not_found(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            404, "ingredient.errors.not_found", request, code="INGREDIENT_NOT_FOUND"
        )

    @staticmethod
    def slug_too_big(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            422, "recipe.errors.slug_too_big", request, code="RECIPE_SLUG_TOO_BIG"
        )

    @staticmethod
    def ingredient_already_exist(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            409,
            "ingredient.errors.already_exist",
            request,
            code="INGREDIENT_ALREADY_EXISTS",
        )

    @staticmethod
    def unsupported_image_type(
        request: Request, content_type: str
    ) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            400,
            "recipe.errors.unsupported_image_type",
            request,
            code="RECIPE_UNSUPPORTED_IMAGE_TYPE",
            content_type=content_type,
        )

    @staticmethod
    def image_too_large(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            400, "recipe.errors.image_too_large", request, code="RECIPE_IMAGE_TOO_LARGE"
        )

    @staticmethod
    def image_not_in_suggestions(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            400,
            "recipe.errors.image_not_in_suggestions",
            request,
            code="RECIPE_IMAGE_NOT_IN_SUGGESTIONS",
        )

    @staticmethod
    def user_id_not_exists(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            422, "recipe.errors.user_not_exists", request, code="USER_NOT_EXISTS"
        )

    @staticmethod
    def import_invalid_json(
        request: Request, message: str
    ) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            400,
            "recipe.errors.import_invalid_json",
            request,
            code="RECIPE_IMPORT_INVALID_JSON",
            message=message,
        )

    @staticmethod
    def import_validation_failed(
        request: Request, message: str
    ) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            400,
            "recipe.errors.import_validation_failed",
            request,
            code="RECIPE_IMPORT_VALIDATION_FAILED",
            message=message,
        )

    @staticmethod
    def service_user_unavailable(request: Request) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            503,
            "http_client.service_user.errors.unavailable",
            request,
            code="SERVICE_USER_UNAVAILABLE",
        )

    @staticmethod
    def service_es_failed(
        request: Request, translation_key: str, e: Exception
    ) -> "LocalizedHTTPException":
        return LocalizedHTTPException(
            500, translation_key, request, code="ELASTICSEARCH_ERROR", message=str(e)
        )
