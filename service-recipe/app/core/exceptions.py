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
