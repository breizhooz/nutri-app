from sqlalchemy import String, ForeignKey
from sqlalchemy import Mapped, mapped_column, relationship

from .recipe import Recipe
from .ingredient import Ingredient
from app.db.base import Base

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float]
    unit: Mapped[str] = mapped_column(String(50))  # g, ml, unité, càs...
    
    # Relations
    recipe: Mapped["Recipe"] = relationship(back_populates="recipe_ingredients")
    ingredient: Mapped["Ingredient"] = relationship()