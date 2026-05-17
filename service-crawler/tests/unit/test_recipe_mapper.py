from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.recipe_mapper import (
    EN_CONFIG,
    FR_CONFIG,
    MULTILINGUAL_CONFIG,
    IngredientParser,
    LanguageConfig,
    ParsedIngredient,
    RecipeMapper,
    _merge,
)


# ── LanguageConfig & _merge ───────────────────────────────────────────────────

class TestLanguageConfig:
    def test_fr_config_has_units_and_connectors(self):
        assert len(FR_CONFIG.units) > 0
        assert len(FR_CONFIG.connectors) > 0
        assert FR_CONFIG.default_unit == "pièce"

    def test_en_config_has_units_and_connectors(self):
        assert len(EN_CONFIG.units) > 0
        assert len(EN_CONFIG.connectors) > 0
        assert EN_CONFIG.default_unit == "piece"

    def test_multilingual_contains_fr_and_en_units(self):
        unit_str = " ".join(MULTILINGUAL_CONFIG.units)
        assert "cuill" in unit_str      # FR
        assert "tablespoon" in unit_str  # EN

    def test_multilingual_contains_fr_and_en_connectors(self):
        connector_str = " ".join(MULTILINGUAL_CONFIG.connectors)
        assert "de" in connector_str   # FR
        assert "of" in connector_str   # EN

    def test_merge_deduplicates_shared_units(self):
        # both FR and EN have "g" and "kg"
        assert MULTILINGUAL_CONFIG.units.count("g") == 1
        assert MULTILINGUAL_CONFIG.units.count("kg") == 1

    def test_merge_sorts_units_longest_first(self):
        merged = _merge(FR_CONFIG, EN_CONFIG, default_unit="unit")
        lengths = [len(u) for u in merged.units]
        assert lengths == sorted(lengths, reverse=True)

    def test_merge_custom_default_unit(self):
        merged = _merge(FR_CONFIG, EN_CONFIG, default_unit="custom")
        assert merged.default_unit == "custom"

    def test_frozen_config_is_immutable(self):
        with pytest.raises(Exception):
            FR_CONFIG.default_unit = "changed"  # type: ignore[misc]


# ── IngredientParser (FR) ─────────────────────────────────────────────────────

class TestIngredientParserFR:
    @pytest.fixture
    def parser(self):
        return IngredientParser(config=FR_CONFIG)

    def test_empty_text_returns_empty(self, parser):
        assert parser.parse("") == []

    def test_whitespace_only_returns_empty(self, parser):
        assert parser.parse("   \n   ") == []

    def test_simple_grams(self, parser):
        items = parser.parse("200g farine")
        assert len(items) == 1
        assert items[0].name.lower() == "farine"
        assert items[0].quantity == 200.0
        assert items[0].unit == "g"

    def test_with_de_connector(self, parser):
        items = parser.parse("250g de beurre")
        assert len(items) == 1
        assert items[0].name.lower() == "beurre"

    def test_space_between_qty_and_unit(self, parser):
        items = parser.parse("250 g de beurre")
        assert items[0].quantity == 250.0

    def test_no_unit_defaults_to_piece(self, parser):
        items = parser.parse("3 oeufs")
        assert len(items) == 1
        assert items[0].unit == "pièce"

    def test_cuillere_a_soupe(self, parser):
        items = parser.parse("2 cuillères à soupe d'huile")
        assert len(items) == 1
        assert "huile" in items[0].name.lower()

    def test_cuillere_a_cafe(self, parser):
        items = parser.parse("1 cuillère à café de sel")
        assert len(items) == 1
        assert items[0].name.lower() == "sel"

    def test_decimal_comma(self, parser):
        items = parser.parse("1,5 kg viande")
        assert items[0].quantity == 1.5

    def test_decimal_dot(self, parser):
        items = parser.parse("0.5 kg sucre")
        assert items[0].quantity == 0.5

    def test_bullet_prefix_hyphen(self, parser):
        assert len(parser.parse("- 200g farine")) == 1

    def test_bullet_prefix_dot(self, parser):
        assert len(parser.parse("• 3 oeufs")) == 1

    def test_multiple_lines(self, parser):
        text = "200g farine\n3 oeufs\n100ml lait"
        assert len(parser.parse(text)) == 3

    def test_deduplication_keeps_first(self, parser):
        items = parser.parse("200g farine\n100g farine")
        assert len(items) == 1
        assert items[0].quantity == 200.0

    def test_non_ingredient_lines_ignored(self, parser):
        text = "Préchauffer le four à 180°C\nMélanger tous les ingrédients"
        assert parser.parse(text) == []

    def test_unit_plural_normalized(self, parser):
        items = parser.parse("3 verres de lait")
        assert items[0].unit == "verre"

    def test_name_too_short_ignored(self, parser):
        assert parser.parse("5g x") == []
    
    def test_backtracking_artifact_ignored(self, parser):
        assert parser.parse("5g x") == []

    def test_short_real_ingredient_passes(self, parser):
        assert len(parser.parse("1 cuillère à café de sel")) == 1


# ── IngredientParser (EN) ─────────────────────────────────────────────────────

class TestIngredientParserEN:
    @pytest.fixture
    def parser(self):
        return IngredientParser(config=EN_CONFIG)

    def test_cups_of_flour(self, parser):
        items = parser.parse("2 cups of flour")
        assert len(items) == 1
        assert items[0].quantity == 2.0
        assert items[0].unit == "cup"
        assert "flour" in items[0].name.lower()

    def test_tablespoons_no_connector(self, parser):
        items = parser.parse("3 tablespoons olive oil")
        assert len(items) == 1
        assert items[0].unit == "tablespoon"
        assert "olive oil" in items[0].name.lower()

    def test_teaspoons(self, parser):
        items = parser.parse("1 teaspoon salt")
        assert items[0].unit == "teaspoon"
        assert items[0].name.lower() == "salt"

    def test_ounces(self, parser):
        items = parser.parse("8 ounces cream cheese")
        assert items[0].unit == "ounce"
        assert items[0].quantity == 8.0

    def test_pounds(self, parser):
        items = parser.parse("1 pound ground beef")
        assert items[0].unit == "pound"

    def test_no_unit_defaults_to_piece(self, parser):
        items = parser.parse("3 eggs")
        assert items[0].unit == "piece"

    def test_cloves(self, parser):
        items = parser.parse("4 cloves garlic")
        assert items[0].unit == "clove"

    def test_bullet_list(self, parser):
        text = "- 2 cups flour\n- 1 teaspoon salt\n- 3 eggs"
        assert len(parser.parse(text)) == 3

    def test_of_connector(self, parser):
        items = parser.parse("1 cup of sugar")
        assert "sugar" in items[0].name.lower()


# ── IngredientParser (multilingual) ──────────────────────────────────────────

class TestIngredientParserMultilingual:
    @pytest.fixture
    def parser(self):
        return IngredientParser()  # uses MULTILINGUAL_CONFIG

    def test_french_line_parsed(self, parser):
        items = parser.parse("200g de farine")
        assert items[0].unit == "g"
        assert "farine" in items[0].name.lower()

    def test_english_line_parsed(self, parser):
        items = parser.parse("2 cups of flour")
        assert items[0].unit == "cup"

    def test_default_unit_is_neutral(self, parser):
        items = parser.parse("3 oeufs")
        assert items[0].unit == MULTILINGUAL_CONFIG.default_unit

    def test_mixed_fr_en_text(self, parser):
        text = "200g de farine\n2 cups of sugar\n3 oeufs"
        items = parser.parse(text)
        assert len(items) == 3

    def test_shared_units_not_duplicated(self, parser):
        # "g" exists in both FR and EN; should only match once
        items = parser.parse("100g butter")
        assert len(items) == 1
        assert items[0].unit == "g"


# ── IngredientParser._normalize_unit ─────────────────────────────────────────

class TestNormalizeUnit:
    def test_single_word_plural_stripped(self):
        assert IngredientParser._normalize_unit("cups") == "cup"
        assert IngredientParser._normalize_unit("tasses") == "tasse"
        assert IngredientParser._normalize_unit("gousses") == "gousse"

    def test_short_units_unchanged(self):
        assert IngredientParser._normalize_unit("g") == "g"
        assert IngredientParser._normalize_unit("ml") == "ml"

    def test_multiword_units_unchanged(self):
        assert IngredientParser._normalize_unit("cuillère à soupe") == "cuillère à soupe"
        assert IngredientParser._normalize_unit("tablespoon") == "tablespoon"

    def test_already_singular_unchanged(self):
        assert IngredientParser._normalize_unit("cup") == "cup"
        assert IngredientParser._normalize_unit("tasse") == "tasse"

    def test_uppercase_lowercased(self):
        assert IngredientParser._normalize_unit("Cups") == "cup"
        assert IngredientParser._normalize_unit("G") == "g"


# ── RecipeMapper ──────────────────────────────────────────────────────────────

class TestRecipeMapper:
    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mapper(self, mock_client):
        return RecipeMapper(mock_client)

    @staticmethod
    def _make_result(
        title: str = "Tarte aux pommes",
        raw_content: str = "200g farine\n3 oeufs",
        url: str = "https://example.com/tarte",
        images: list | None = None,
    ) -> MagicMock:
        r = MagicMock()
        r.title = title
        r.raw_content = raw_content
        r.url_origin = url
        r.images = images if images is not None else []
        return r

    async def test_map_and_send_returns_recipe_dict(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.return_value = 1
        mock_client.create_recipe.return_value = {"id": 42}
        result = await mapper.map_and_send(self._make_result())
        assert result == {"id": 42}

    async def test_map_and_send_calls_create_recipe_once(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.return_value = 1
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result())
        mock_client.create_recipe.assert_called_once()

    async def test_map_and_send_resolves_each_ingredient(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.side_effect = [1, 2]
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(raw_content="200g farine\n3 oeufs"))
        assert mock_client.get_or_create_ingredient.call_count == 2

    async def test_empty_content_sends_empty_ingredients(self, mapper, mock_client):
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(raw_content=""))
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["recipe_ingredients"] == []

    async def test_none_content_treated_as_empty(self, mapper, mock_client):
        mock_client.create_recipe.return_value = {}
        r = self._make_result()
        r.raw_content = None
        await mapper.map_and_send(r)
        mock_client.create_recipe.assert_called_once()

    async def test_failed_ingredient_is_skipped(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.side_effect = [
            1,
            httpx.RequestError("timeout", request=MagicMock()),
        ]
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(raw_content="200g farine\n3 oeufs"))
        payload = mock_client.create_recipe.call_args[0][0]
        assert len(payload["recipe_ingredients"]) == 1

    async def test_http_status_error_on_ingredient_skipped(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(raw_content="200g farine"))
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["recipe_ingredients"] == []

    async def test_payload_uses_first_image(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.return_value = 1
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(
            self._make_result(images=["https://img1.com/a.jpg", "https://img2.com/b.jpg"])
        )
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["image_url"] == "https://img1.com/a.jpg"

    async def test_payload_image_url_none_when_no_images(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.return_value = 1
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(images=[]))
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["image_url"] is None

    async def test_payload_title_fallback_when_empty(self, mapper, mock_client):
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(title="", raw_content=""))
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["title"] == "Recette importée"

    async def test_recipe_ingredients_structure(self, mapper, mock_client):
        mock_client.get_or_create_ingredient.return_value = 5
        mock_client.create_recipe.return_value = {}
        await mapper.map_and_send(self._make_result(raw_content="200g farine"))
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["recipe_ingredients"] == [
            {"ingredient_id": 5, "quantity": 200.0, "unit": "g"}
        ]

    async def test_custom_parser_injected(self, mock_client):
        custom_parser = IngredientParser(config=EN_CONFIG)
        mapper = RecipeMapper(mock_client, parser=custom_parser)
        mock_client.get_or_create_ingredient.return_value = 1
        mock_client.create_recipe.return_value = {}
        r = self._make_result(raw_content="2 cups flour")
        await mapper.map_and_send(r)
        payload = mock_client.create_recipe.call_args[0][0]
        assert payload["recipe_ingredients"][0]["unit"] == "cup"
    