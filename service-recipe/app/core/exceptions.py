"""Framework-agnostic domain errors raised by the service layer.

Services must not depend on FastAPI's ``Request`` (needed for i18n), so they
raise these plain exceptions. Dedicated handlers (see ``app/core/error_handlers``)
translate them into localized HTTP responses at the edge.
"""


class DomainError(Exception):
    """Base class for service-layer domain errors."""


class RecipeNotFound(DomainError):
    pass


class RecipeForbidden(DomainError):
    """The current user is not the author of the recipe."""


class SlugGenerationError(DomainError):
    """No unique slug could be generated for a title."""


class IngredientNotFound(DomainError):
    pass


class IngredientAlreadyExists(DomainError):
    pass


class UnsupportedImageType(DomainError):
    """The uploaded image has a content type that is not allowed."""

    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(content_type)


class ImageTooLarge(DomainError):
    """The uploaded image exceeds the maximum allowed size."""


class ImageNotInSuggestions(DomainError):
    """The selected image is not part of the recipe's proposed suggestions."""


class ImageServiceUnavailable(DomainError):
    """The image provider (Unsplash) is unreachable or rate-limited."""
