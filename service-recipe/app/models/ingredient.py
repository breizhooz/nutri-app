from typing import Optional, Any
from sqlalchemy import String, Integer, ForeignKey, func, JSON, Float,  Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.models.enums import TypeOfIngredient, Allergen, Nutrition, Diet
from app.db.base_class import Base

class Ingredient(Base):
    """Ingredient Model"""
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name:  Mapped[str] = mapped_column(String(200), unique=True)

    # Utilisation de ARRAY avec le type natif Enum de SQLAlchemy
    # On utilise String comme type de base pour stocker la valeur "enums.type..."
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), 
        default=[],
        server_default="{}",
        comment="List of tags issus from Enums"
    )

    @validates("tags")
    def validate_tags(self, key, tags_list):
        """
        Validate tags data, need to be Enum TypeOfIngredient, Allergen, Nutrition, Diet

        Raise: 
            ValueError: if value doesn't exist
        """
        if not tags_list:
            return tags_list

        allowed_values = {
            *[e.value for e in TypeOfIngredient],
            *[e.value for e in Allergen],
            *[e.value for e in Nutrition],
            *[e.value for e in Diet],
        }

        for tag in tags_list:
            if tag not in allowed_values:
                raise ValueError(
                    f"tags '{tag}' is not valid value "
                    f"Expected values from TypeOfIngredient, Allergen, Nutrition ou Diet."
                )
        
        return tags_list
    
    free_tags: Mapped[list[str]] = mapped_column(
        JSON, 
        default=[], 
        server_default="[]"
    )

    calories_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    proteins_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbs_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fats_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)