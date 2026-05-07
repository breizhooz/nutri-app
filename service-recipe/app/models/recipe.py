from typing import Any
from sqlalchemy import String, Text, Integer, ForeignKey, func, JSON,  Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.db.base_class import Base
from app.models.enums import DifficultyLevel, RecipeOrigin, CuisineOrigin
from app.models.recipe_ingredients import RecipeIngredient


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)

    #base structure
    title: Mapped[str] = mapped_column(String(300))
    slug: Mapped[str] = mapped_column(String(350), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)

    #timing
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer)
    servings: Mapped[int] = mapped_column(Integer, default=4)

    #classification
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        SQLEnum(DifficultyLevel, native_enum=False, length=50),
        default = DifficultyLevel.EASY
    )

    tags: Mapped[dict[str, Any]] = mapped_column(
        JSON, 
        default={}, 
        server_default="{}"
    )

    cuisine_origin:  Mapped[CuisineOrigin] = mapped_column(
        SQLEnum(CuisineOrigin, native_enum=False, length=50),
        default = CuisineOrigin.FRENCH
    )
    #origin of the recipe
    origin_recipe: Mapped[RecipeOrigin] = mapped_column(
        SQLEnum(RecipeOrigin, native_enum=False, length=50),
        default = RecipeOrigin.PERSONAL
    )
    book_name: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(500))

    image_url: Mapped[str | None] = mapped_column(String(500))

    #metadata
    created_by_user_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default= func.now(),
        onupdate= func.now()
    )

    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(back_populates="recipe")


