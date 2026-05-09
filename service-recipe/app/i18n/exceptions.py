from fastapi import HTTPException, Request, status
from app.i18n.loader import t

class LocalizedHTTPException(HTTPException):
    """
    overload translation for exception
    """

    def __init__(self, status_code: int, translation_key: str, request: Request, **kwargs):
        locale = getattr(request.state, "locale", "fr")
        detail = t.get(translation_key, locale=locale, **kwargs)
        super().__init__(status_code=status_code, detail=detail)

    #helpers recipe
    @staticmethod
    def recipe_not_found(request: Request) -> HTTPException:
        return LocalizedHTTPException(404, "recipe.errors.not_found", request)
    
    @staticmethod
    def unauthorized(request: Request) -> HTTPException:
        return LocalizedHTTPException(403, "recipe.error.unauthorized", request)
    
    #helpers recipe
    @staticmethod
    def ingredient_not_found(request: Request) -> HTTPException:
        return LocalizedHTTPException(404, "ingredient.errors.not_found", request)
    
    @staticmethod
    def ingredient_already_exist(request: Request) -> HTTPException:
        return LocalizedHTTPException(409, "ingredient.errors.already_exist", request)

    @staticmethod
    def user_id_not_exists(request: Request) -> HTTPException:
        return LocalizedHTTPException(422, "recipe.errors.user_not_exists", request)

    @staticmethod
    def service_user_unavailable(request: Request) -> HTTPException:
        return LocalizedHTTPException(503, "http_client.service_user.errors.unavailable", request)
