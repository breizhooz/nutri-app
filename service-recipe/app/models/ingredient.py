from typing import Optional, Any
from sqlalchemy import String, Integer, ForeignKey, func, JSON, Float,  Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import TypeOfIngredient, Allergen, Nutrition, Diet
from app.db.base_class import Base

class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name:  Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    # Utilisation de ARRAY avec le type natif Enum de SQLAlchemy
    # On utilise String comme type de base pour stocker la valeur "enums.type..."
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), 
        default=[],
        server_default="{}",
        comment="List of tags issus from Enums"
    )
    
    free_tags: Mapped[dict[str, Any]] = mapped_column(
        JSON, 
        default={}, 
        server_default="{}"
    )

    calories_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    proteins_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    carbs_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fats_per_100g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)