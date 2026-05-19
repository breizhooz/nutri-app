from enum import Enum as PyEnum


class NutritionSource(str, PyEnum):
    ciqual = "ciqual"
    open_food_facts = "open_food_facts"
    user = "user"
    # uppercase aliases for backward compatibility
    CIQUAL = "ciqual"
    USER = "user"


class MacroErrorStatus(str, PyEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    MANUAL = "manual"