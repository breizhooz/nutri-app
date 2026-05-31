from app.core.exceptions import IngredientAlreadyExists, IngredientNotFound
from app.models.ingredient import Ingredient
from app.repositories.ingredient_repository import IngredientRepository
from app.schemas.ingredient import IngredientCreate, IngredientUpdate


class IngredientService:
    def __init__(self, repository: IngredientRepository) -> None:
        self._repository = repository

    async def create(self, data: IngredientCreate) -> Ingredient:
        if await self._repository.get_by_name(data.name) is not None:
            raise IngredientAlreadyExists()
        return await self._repository.create(Ingredient(**data.model_dump()))

    async def list(self, skip: int = 0, limit: int = 100) -> list[Ingredient]:
        return await self._repository.list(skip, limit)

    async def get(self, ingredient_id: int) -> Ingredient:
        ingredient = await self._repository.get_by_id(ingredient_id)
        if ingredient is None:
            raise IngredientNotFound()
        return ingredient

    async def update(self, ingredient_id: int, data: IngredientUpdate) -> Ingredient:
        ingredient = await self._repository.get_by_id(ingredient_id)
        if ingredient is None:
            raise IngredientNotFound()
        fields = data.model_dump(exclude_unset=True)
        return await self._repository.update(ingredient, fields)

    async def delete(self, ingredient_id: int) -> None:
        ingredient = await self._repository.get_by_id(ingredient_id)
        if ingredient is None:
            raise IngredientNotFound()
        await self._repository.delete(ingredient)
