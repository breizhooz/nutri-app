import json
from unittest.mock import patch

from app.services.recipe_mapper import IngredientParser
from app.services.recipe_schema_extractor import RecipeSchemaExtractor

_URL = "https://blog-inconnu.example/crepes"


def _page(ld: dict | None, body: str = "<div id='root'></div>") -> str:
    script = (
        f'<script type="application/ld+json">{json.dumps(ld)}</script>' if ld else ""
    )
    return f"<html><head><title>Titre page</title>{script}</head><body>{body}</body></html>"


_FULL = {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Crêpes",
    "description": "Faciles et rapides",
    "recipeYield": "4",
    "prepTime": "PT10M",
    "cookTime": "PT20M",
    "image": "https://ex.com/crepes.jpg",
    "recipeIngredient": ["250 g de farine", "3 oeufs", "50 cl de lait"],
    "recipeInstructions": [
        {"@type": "HowToStep", "text": "Mélanger la farine et les oeufs."},
        {"@type": "HowToStep", "text": "Cuire 2 minutes par face."},
    ],
}


def test_extract_full_json_ld_recipe():
    result = RecipeSchemaExtractor().extract(_URL, _page(_FULL))

    assert result is not None
    assert result["title"] == "Crêpes"
    assert result["images"] == ["https://ex.com/crepes.jpg"]
    assert result["video_url"] is None
    content = result["raw_content"]
    assert "Faciles et rapides" in content
    assert "Préparation : 10 min" in content
    assert "Cuisson : 20 min" in content
    assert "- 250 g de farine" in content
    assert "Étape 1 : Mélanger la farine et les oeufs." in content
    assert "Étape 2 : Cuire 2 minutes par face." in content


def test_extract_returns_none_without_schema():
    html = "<html><body><article>Un article sans recette.</article></body></html>"
    assert RecipeSchemaExtractor().extract(_URL, html) is None


def test_extract_returns_none_when_no_ingredients_nor_steps():
    ld = {"@context": "https://schema.org", "@type": "Recipe", "name": "Vide"}
    assert RecipeSchemaExtractor().extract(_URL, _page(ld)) is None


def test_extract_tolerates_missing_optional_fields():
    ld = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Minimal",
        "recipeIngredient": ["1 pomme"],
    }
    result = RecipeSchemaExtractor().extract(_URL, _page(ld))

    assert result is not None
    assert result["title"] == "Minimal"
    assert result["images"] == []
    assert "- 1 pomme" in result["raw_content"]
    assert "Instructions" not in result["raw_content"]
    assert "Préparation" not in result["raw_content"]


def test_extract_returns_none_when_library_crashes():
    with patch(
        "app.services.recipe_schema_extractor.scrape_html",
        side_effect=RuntimeError("HTML inattendu"),
    ):
        assert RecipeSchemaExtractor().extract(_URL, _page(_FULL)) is None


def test_field_returns_none_when_getter_raises():
    def _boom():
        raise ValueError("champ absent")

    assert RecipeSchemaExtractor._field(_boom) is None
    assert RecipeSchemaExtractor._field(lambda: "ok") == "ok"


def test_formatted_steps_are_not_parsed_as_ingredients():
    """Le mapper parse raw_content ligne à ligne (quantité/unité/nom) : les étapes
    ne doivent pas y apparaître comme des ingrédients."""
    result = RecipeSchemaExtractor().extract(_URL, _page(_FULL))

    names = [i.name.lower() for i in IngredientParser().parse(result["raw_content"])]
    assert any("farine" in n for n in names)
    assert not any("cuire" in n or "mélanger" in n for n in names)
