import pytest
from pydantic import ValidationError

from app.schemas.recipe_import import (
    IngredientImport,
    RecipeImportPayload,
)

VALID_TAG = "enums.type_of_ingredient.rice"


# ─── IngredientImport.tags ──────────────────────────────────────────────────────


class TestIngredientTagsValidation:
    def test_accepts_valid_enum_tag(self):
        ing = IngredientImport(name="riz", tags=[VALID_TAG])
        assert ing.tags == [VALID_TAG]

    def test_accepts_empty_tags(self):
        ing = IngredientImport(name="riz")
        assert ing.tags == []

    def test_rejects_unknown_tag(self):
        with pytest.raises(ValidationError) as exc:
            IngredientImport(name="riz", tags=["not.a.real.tag"])
        assert "tags invalides" in str(exc.value)


# ─── RecipeImportPayload catalog consistency ─────────────────────────────────────


def _payload(**kwargs) -> dict:
    defaults = dict(
        created_by_user_id="user-1",
        ingredients=[{"name": "riz", "calories_per_100g": 356.0}],
        recipes=[
            {
                "title": "Risotto",
                "instructions": "x",
                "ingredients": [{"name": "riz", "quantity": 300.0, "unit": "g"}],
            }
        ],
    )
    defaults.update(kwargs)
    return defaults


class TestPayloadCatalogConsistency:
    def test_accepts_when_all_ingredients_in_catalog(self):
        payload = RecipeImportPayload.model_validate(_payload())
        assert len(payload.recipes) == 1

    def test_rejects_recipe_ingredient_absent_from_catalog(self):
        data = _payload(
            recipes=[
                {
                    "title": "Risotto",
                    "instructions": "x",
                    "ingredients": [
                        {"name": "parmesan", "quantity": 60.0, "unit": "g"}
                    ],
                }
            ]
        )
        with pytest.raises(ValidationError) as exc:
            RecipeImportPayload.model_validate(data)
        message = str(exc.value)
        assert "absents du catalogue" in message
        assert "parmesan" in message

    def test_requires_created_by_user_id(self):
        data = _payload()
        del data["created_by_user_id"]
        with pytest.raises(ValidationError):
            RecipeImportPayload.model_validate(data)

    def test_rejects_non_object_root(self):
        with pytest.raises(ValidationError):
            RecipeImportPayload.model_validate(["not", "an", "object"])

    def test_rejects_invalid_enum_value(self):
        data = _payload(
            recipes=[
                {
                    "title": "Risotto",
                    "instructions": "x",
                    "difficulty": "enums.difficulty.impossible",
                    "ingredients": [{"name": "riz", "quantity": 300.0, "unit": "g"}],
                }
            ]
        )
        with pytest.raises(ValidationError):
            RecipeImportPayload.model_validate(data)
