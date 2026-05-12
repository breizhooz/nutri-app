from typing import Any
from sqlalchemy import String, Text, Integer, Date, JSON, Enum as SQLEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from datetime import date

from app.models.abstract_model import AbstractModel
from app.models.enums import Allergen
from .menu_slot import MenuSlot


class WeeklyMenu(AbstractModel):
    __tablename__ = "weekly_menus"

    slug: Mapped[str | None] = mapped_column(String(350), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))

    nb_persons: Mapped[int] = mapped_column(Integer, default=1)
    caloric_target: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)

    exclusions: Mapped[list[Any]] = mapped_column(JSON, default=[], server_default="[]")

    @validates("exclusions")
    def validate_exclusions(self, key, value):
        return self._generic_enum_validator(key, value, Allergen)

    free_tags: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, server_default="{}")
    notes: Mapped[str | None] = mapped_column(Text)

    rating: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_weekly_menus_rating"),
    )

    slots: Mapped[list["MenuSlot"]] = relationship(
        back_populates="menu", cascade="all, delete-orphan"
    )