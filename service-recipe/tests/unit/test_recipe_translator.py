from app.services.recipe_translator import RecipeTranslator

_FR = {
    "Spaghetti Carbonara": "Spaghetti Carbonara",
    "A classic Italian pasta.": "Une pâte italienne classique.",
    "olive oil": "huile d'olive",
    "2 cloves garlic": "2 gousses d'ail",
    "garlic": "ail",
    "Boil the pasta.": "Faire bouillir les pâtes.",
}


def _fake_batch(texts):
    return [_FR.get(t, f"FR::{t}") for t in texts]


def _payload():
    return {
        "id": 1,
        "title": "Spaghetti Carbonara",
        "summary": "A <b>classic</b> Italian pasta.",
        "dishTypes": ["main course"],
        "cuisines": ["Italian"],
        "extendedIngredients": [
            {"original": "2 cloves garlic", "name": "garlic", "nameClean": "garlic"},
        ],
        "analyzedInstructions": [{"steps": [{"number": 1, "step": "Boil the pasta."}]}],
    }


class TestTranslatePayload:
    def test_translates_text_fields(self):
        tr = RecipeTranslator(enabled=True, translate_batch=_fake_batch)
        out = tr.translate_payload(_payload())
        assert out["title"] == "Spaghetti Carbonara"
        assert out["summary"] == "Une pâte italienne classique."  # HTML strippé + FR
        assert out["extendedIngredients"][0]["original"] == "2 gousses d'ail"
        assert out["extendedIngredients"][0]["name"] == "ail"
        assert out["analyzedInstructions"][0]["steps"][0]["step"] == "Faire bouillir les pâtes."

    def test_keeps_dish_types_and_cuisines_in_english(self):
        # Le mapper en dépend pour course_type / cuisine_origin.
        tr = RecipeTranslator(enabled=True, translate_batch=_fake_batch)
        out = tr.translate_payload(_payload())
        assert out["dishTypes"] == ["main course"]
        assert out["cuisines"] == ["Italian"]

    def test_disabled_is_identity(self):
        original = _payload()
        tr = RecipeTranslator(enabled=False, translate_batch=_fake_batch)
        assert tr.translate_payload(original) is original

    def test_does_not_mutate_input(self):
        original = _payload()
        tr = RecipeTranslator(enabled=True, translate_batch=_fake_batch)
        tr.translate_payload(original)
        assert original["title"] == "Spaghetti Carbonara"
        assert original["summary"] == "A <b>classic</b> Italian pasta."

    def test_dedupes_sources(self):
        seen = []

        def batch(texts):
            seen.append(list(texts))
            return [t.upper() for t in texts]

        payload = {
            "title": "garlic",
            "extendedIngredients": [
                {"name": "garlic"},
                {"name": "garlic"},
            ],
        }
        RecipeTranslator(enabled=True, translate_batch=batch).translate_payload(payload)
        assert seen == [["garlic"]]  # une seule occurrence envoyée

    def test_batch_failure_returns_original(self):
        def boom(_texts):
            raise RuntimeError("google down")

        original = _payload()
        tr = RecipeTranslator(enabled=True, translate_batch=boom)
        assert tr.translate_payload(original) is original  # fallback EN

    def test_empty_payload_noop(self):
        tr = RecipeTranslator(enabled=True, translate_batch=_fake_batch)
        assert tr.translate_payload({}) == {}
