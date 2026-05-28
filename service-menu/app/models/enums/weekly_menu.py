from enum import Enum as PyEnum


class DayOfWeek(str, PyEnum):
    MONDAY = "enums.day.monday"
    TUESDAY = "enums.day.tuesday"
    WEDNESDAY = "enums.day.wednesday"
    THURSDAY = "enums.day.thursday"
    FRIDAY = "enums.day.friday"
    SATURDAY = "enums.day.saturday"
    SUNDAY = "enums.day.sunday"


class MealType(str, PyEnum):
    BREAKFAST = "enums.meal_type.breakfast"
    MORNING_SNACK = "enums.meal_type.morning_snack"
    LUNCH = "enums.meal_type.lunch"
    AFTERNOON_SNACK = "enums.meal_type.afternoon_snack"
    DINNER = "enums.meal_type.dinner"
