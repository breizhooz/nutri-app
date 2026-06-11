from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    Date,
    JSON,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from datetime import date

from app.models.abstract_model import AbstractModel
from app.models.enums import Allergen
from .menu_slot import MenuSlot


class WeeklyMenu(AbstractModel):
    __tablename__ = "weekly_menus"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "start_date", name="uq_weekly_menus_user_start_date"
        ),
    )

    slug: Mapped[str | None] = mapped_column(String(350), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36))
    # Multicomptes (CRM) : clé de partition (act_account du JWT). Filtre d'accès =
    # account_id ; user_id reste = auteur/legacy. Backfill cross-DB depuis les
    # memberships OWNER de service-user.
    account_id: Mapped[str | None] = mapped_column(String(36), index=True)

    nb_persons: Mapped[int] = mapped_column(Integer, default=1)
    caloric_target: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)

    exclusions: Mapped[list[Any]] = mapped_column(JSON, default=[], server_default="[]")

    @validates("exclusions")
    def validate_exclusions(self, key, value):
        return self._generic_enum_validator(key, value, Allergen)

    free_tags: Mapped[dict[str, Any]] = mapped_column(
        JSON, default={}, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    rating: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_weekly_menus_rating"),
    )

    slots: Mapped[list["MenuSlot"]] = relationship(
        back_populates="menu", cascade="all, delete-orphan"
    )
