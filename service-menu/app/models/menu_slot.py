from sqlalchemy import Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.abstract_model import AbstractModel
from app.models.enums import DayOfWeek, MealType


class MenuSlot(AbstractModel):
    __tablename__ = "menu_slots"

    menu_id: Mapped[int] = mapped_column(ForeignKey("weekly_menus.id"), index=True)

    day_of_week: Mapped[DayOfWeek] = mapped_column(
        SQLEnum(DayOfWeek, native_enum=False, length=50)
    )
    @validates("day_of_week")
    def validate_day(self, key, value):
        return self._generic_enum_validator(key, value, DayOfWeek)

    meal_type: Mapped[MealType] = mapped_column(
        SQLEnum(MealType, native_enum=False, length=50)
    )
    @validates("meal_type")
    def validate_meal(self, key, value):
        return self._generic_enum_validator(key, value, MealType)

    recipe_id: Mapped[int] = mapped_column(Integer)

    menu: Mapped["WeeklyMenu"] = relationship(back_populates="slots")
