from typing import Any
from sqlalchemy import String, Text, Integer, Float, func, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from datetime import datetime

from app.models.abstract_model import AbstractModel
from app.models.enums import DifficultyLevel, RecipeOrigin, CuisineOrigin, CourseType
from app.models.recipe_ingredients import RecipeIngredient


class Recipe(AbstractModel):
    """
    Model for the recipe
    """

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # base structure
    title: Mapped[str] = mapped_column(String(300))
    slug: Mapped[str] = mapped_column(String(350), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)

    # timing
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer)
    servings: Mapped[int] = mapped_column(Integer, default=4)

    # classification
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        SQLEnum(DifficultyLevel, native_enum=False, length=50),
        default=DifficultyLevel.EASY,
    )

    @validates("difficulty")
    def validate_difficuty(self, key, val):
        """Check enmu DifficultyLevel"""
        return self._generic_enum_validator(key, val, DifficultyLevel)

    tags: Mapped[dict[str, Any]] = mapped_column(JSON, default={}, server_default="{}")
    free_tags: Mapped[list[str]] = mapped_column(JSON, default=[], server_default="[]")

    cuisine_origin: Mapped[CuisineOrigin] = mapped_column(
        SQLEnum(CuisineOrigin, native_enum=False, length=50),
        default=CuisineOrigin.FRENCH,
    )

    @validates("cuisine_origin")
    def validate_cuisine(self, key, val):
        """Check enmu cuisine_origin"""
        return self._generic_enum_validator(key, val, CuisineOrigin)

    # origin of the recipe
    origin_recipe: Mapped[RecipeOrigin] = mapped_column(
        SQLEnum(RecipeOrigin, native_enum=False, length=50),
        default=RecipeOrigin.PERSONAL,
    )

    @validates("origin_recipe")
    def validate_origin_recipe(self, key, val):
        """Check enmu origin_recipe"""
        return self._generic_enum_validator(key, val, RecipeOrigin)

    # origin of the recipe
    course_type: Mapped[CourseType] = mapped_column(
        SQLEnum(CourseType, native_enum=False, length=50), default=CourseType.STARTER
    )

    @validates("course_type")
    def validate_cuourse_type(self, key, val):
        """Check enmu origin_recipe"""
        return self._generic_enum_validator(key, val, CourseType)

    book_name: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)

    # image_url = image finale validée (HD). image_thumb_url = sa miniature.
    image_url: Mapped[str | None] = mapped_column(Text)
    image_thumb_url: Mapped[str | None] = mapped_column(Text)

    # Propositions Unsplash temporaires (liste de dicts : voir ImageSuggestion).
    image_suggestions: Mapped[list[Any]] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    # Mot-clé de recherche d'images (titre par défaut, ou saisie libre de l'utilisateur).
    image_search_keyword: Mapped[str | None] = mapped_column(String(300))

    # nutrition (per serving, calculated by service-nutrition)
    calories_per_serving: Mapped[float | None] = mapped_column(Float, nullable=True)
    proteins_per_serving: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_per_serving: Mapped[float | None] = mapped_column(Float, nullable=True)
    fats_per_serving: Mapped[float | None] = mapped_column(Float, nullable=True)

    # user feedback on the recipe
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @validates("rating")
    def validate_rating(self, key, val):
        """Rating is a note out of 5 (1..5) or None when unrated."""
        if val is None:
            return val
        if not isinstance(val, int) or not 1 <= val <= 5:
            raise ValueError(f"'{val}' n'est pas une note valide pour {key} (1 à 5).")
        return val

    # metadata
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", passive_deletes=True
    )
