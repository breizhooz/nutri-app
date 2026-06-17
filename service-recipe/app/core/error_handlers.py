"""Translate service-layer domain errors into localized HTTP responses.

Keeps the routes thin and the services free of any ``Request``/i18n coupling:
the ``request`` is only available here, at the framework edge.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ImageNotInSuggestions,
    ImageServiceUnavailable,
    ImageTooLarge,
    IngredientAlreadyExists,
    IngredientNotFound,
    RecipeForbidden,
    RecipeNotFound,
    SlugGenerationError,
    UnsupportedImageType,
)
from app.i18n import LocalizedHTTPException


def _localized_response(exc: LocalizedHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.detail}},
    )


def register_domain_handlers(app: FastAPI) -> None:
    @app.exception_handler(RecipeNotFound)
    async def _recipe_not_found(request: Request, exc: RecipeNotFound) -> JSONResponse:
        return _localized_response(LocalizedHTTPException.recipe_not_found(request))

    @app.exception_handler(RecipeForbidden)
    async def _recipe_forbidden(request: Request, exc: RecipeForbidden) -> JSONResponse:
        return _localized_response(LocalizedHTTPException.unauthorized(request))

    @app.exception_handler(SlugGenerationError)
    async def _slug_error(request: Request, exc: SlugGenerationError) -> JSONResponse:
        return _localized_response(LocalizedHTTPException.slug_too_big(request))

    @app.exception_handler(IngredientNotFound)
    async def _ingredient_not_found(
        request: Request, exc: IngredientNotFound
    ) -> JSONResponse:
        return _localized_response(LocalizedHTTPException.ingredient_not_found(request))

    @app.exception_handler(IngredientAlreadyExists)
    async def _ingredient_exists(
        request: Request, exc: IngredientAlreadyExists
    ) -> JSONResponse:
        return _localized_response(
            LocalizedHTTPException.ingredient_already_exist(request)
        )

    @app.exception_handler(UnsupportedImageType)
    async def _unsupported_image_type(
        request: Request, exc: UnsupportedImageType
    ) -> JSONResponse:
        return _localized_response(
            LocalizedHTTPException.unsupported_image_type(request, exc.content_type)
        )

    @app.exception_handler(ImageTooLarge)
    async def _image_too_large(request: Request, exc: ImageTooLarge) -> JSONResponse:
        return _localized_response(LocalizedHTTPException.image_too_large(request))

    @app.exception_handler(ImageNotInSuggestions)
    async def _image_not_in_suggestions(
        request: Request, exc: ImageNotInSuggestions
    ) -> JSONResponse:
        return _localized_response(
            LocalizedHTTPException.image_not_in_suggestions(request)
        )

    @app.exception_handler(ImageServiceUnavailable)
    async def _image_service_unavailable(
        request: Request, exc: ImageServiceUnavailable
    ) -> JSONResponse:
        return _localized_response(
            LocalizedHTTPException.image_service_unavailable(request)
        )
