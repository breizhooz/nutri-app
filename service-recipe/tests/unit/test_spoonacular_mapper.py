from app.models.enums import CourseType, CuisineOrigin, RecipeOrigin
from app.services.spoonacular_mapper import (
    short_description,
    spoonacular_to_import_item,
    strip_html,
)


def _payload(**over) -> dict:
    base = {
        "id": 42,
        "title": "Spaghetti Carbonara",
        "image": "http://img/42.jpg",
        "sourceUrl": "http://src/42",
        "servings": 2,
        "readyInMinutes": 25,
        "preparationMinutes": 10,
        "cookingMinutes": 15,
        "summary": "A <b>classic</b> Italian pasta with eggs &amp; cheese.",
        "dishTypes": ["lunch", "main course"],
        "cuisines": ["Italian"],
        "extendedIngredients": [
            {
                "name": "spaghetti",
                "nameClean": "spaghetti",
                "amount": 200,
                "unit": "g",
                "measures": {"metric": {"amount": 200.0, "unitShort": "g"}},
            },
            {
                "name": "eggs",
                "amount": 2,
                "unit": "",
                "measures": {"metric": {"amount": 2.0, "unitShort": ""}},
            },
        ],
        "analyzedInstructions": [
            {"steps": [{"step": "Boil the pasta."}, {"step": "Mix with eggs."}]}
        ],
    }
    base.update(over)
    return base


class TestHelpers:
    def test_strip_html_removes_tags_and_entities(self):
        assert strip_html("A <b>bold</b> &amp; clean") == "A bold & clean"

    def test_short_description_truncates_cleanly(self):
        text = "word " * 100
        out = short_description({"summary": text}, max_len=20)
        assert len(out) <= 21 and out.endswith("…")


class TestMapping:
    def test_maps_core_fields(self):
        item = spoonacular_to_import_item(_payload())
        assert item.title == "Spaghetti Carbonara"
        assert item.servings == 2
        assert item.prep_time_minutes == 10
        assert item.cook_time_minutes == 15
        assert item.image_url == "http://img/42.jpg"
        assert item.source_url == "http://src/42"
        assert item.origin_recipe == RecipeOrigin.WEB
        assert item.course_type == CourseType.MAIN_COURSE
        assert item.cuisine_origin == CuisineOrigin.ITALIAN
        assert "spoonacular" in item.free_tags

    def test_description_is_clean_text(self):
        item = spoonacular_to_import_item(_payload())
        assert item.description == "A classic Italian pasta with eggs & cheese."

    def test_instructions_numbered_from_analyzed_steps(self):
        item = spoonacular_to_import_item(_payload())
        assert item.instructions == "1. Boil the pasta.\n2. Mix with eggs."

    def test_ingredients_use_metric_measures(self):
        item = spoonacular_to_import_item(_payload())
        assert [(i.name, i.quantity, i.unit) for i in item.ingredients] == [
            ("spaghetti", 200.0, "g"),
            ("eggs", 2.0, ""),
        ]

    def test_negative_times_become_none(self):
        item = spoonacular_to_import_item(
            _payload(preparationMinutes=-1, cookingMinutes=-1, readyInMinutes=30)
        )
        assert item.prep_time_minutes is None
        assert item.cook_time_minutes == 30  # retombe sur readyInMinutes

    def test_defaults_when_payload_sparse(self):
        item = spoonacular_to_import_item({"id": 1, "title": "Plat"})
        assert item.servings == 4
        assert item.course_type == CourseType.MAIN_COURSE
        assert item.cuisine_origin == CuisineOrigin.AMERICAN
        assert item.ingredients == []

    def test_skips_ingredient_without_name(self):
        item = spoonacular_to_import_item(
            _payload(extendedIngredients=[{"amount": 1, "unit": "g"}])
        )
        assert item.ingredients == []
