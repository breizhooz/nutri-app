"""Tests Étape 3 — construction de la requête Elasticsearch & scoring."""

import pytest

from app.schemas.engine import FilterPriority, FinalTargets, TargetTolerance
from app.services.engine.step3_search_query import SearchQueryBuilder


@pytest.fixture
def builder() -> SearchQueryBuilder:
    return SearchQueryBuilder()


def _targets(filter_priorities=None) -> FinalTargets:
    return FinalTargets(
        calories=2000,
        proteines=160,
        lipides=55.6,
        glucides=215,
        tolerances=TargetTolerance(),
        filter_priorities=filter_priorities or [],
    )


def _bool(query: dict) -> dict:
    return query["query"]["function_score"]["query"]["bool"]


def _functions(query: dict) -> list[dict]:
    return query["query"]["function_score"]["functions"]


class TestSearchQueryBuilder:
    @pytest.mark.unit
    def test_top_level_structure(self, builder) -> None:
        q = builder.build(_targets(), [], "standard", [])
        fs = q["query"]["function_score"]
        assert fs["score_mode"] == "sum"
        assert fs["boost_mode"] == "replace"

    @pytest.mark.unit
    def test_exclusions_in_must_not(self, builder) -> None:
        """Aliments exclus + contre-indications + régime éthique → must_not."""
        q = builder.build(_targets(), ["arachide"], "vegan", ["lactose"])
        must_not = _bool(q)["must_not"]
        flat = str(must_not)
        assert "arachide" in flat
        assert "lactose" in flat
        assert "viande" in flat  # banni par le régime vegan
        assert len(must_not) == 3

    @pytest.mark.unit
    def test_standard_diet_has_no_diet_ban(self, builder) -> None:
        q = builder.build(_targets(), [], "standard", [])
        assert _bool(q)["must_not"] == []

    @pytest.mark.unit
    def test_strict_priority_becomes_filter(self, builder) -> None:
        fps = [FilterPriority(field_name="cooking_time", is_strict=True)]
        q = builder.build(_targets(fps), [], "standard", [])
        filters = _bool(q)["filter"]
        assert {"exists": {"field": "cooking_time"}} in filters
        # ...et jamais en fonction de scoring
        assert all("cooking_time" not in str(fn) for fn in _functions(q))

    @pytest.mark.unit
    def test_soft_priority_becomes_scoring_only(self, builder) -> None:
        fps = [FilterPriority(field_name="budget", is_strict=False, ui_weight=2.0)]
        q = builder.build(_targets(fps), [], "standard", [])
        # jamais en filter
        assert all("budget" not in str(f) for f in _bool(q)["filter"])
        # présent en scoring avec le poids UI
        budget_fn = [fn for fn in _functions(q) if "budget" in str(fn)]
        assert len(budget_fn) == 1
        assert budget_fn[0]["weight"] == 2.0

    @pytest.mark.unit
    def test_macro_proximity_functions_present(self, builder) -> None:
        """4 fonctions de proximité : calories + 3 macros."""
        q = builder.build(_targets(), [], "standard", [])
        fns = _functions(q)
        fields = {list(fn["gauss"].keys())[0] for fn in fns if "gauss" in fn}
        assert fields == {"calories", "proteines", "lipides", "glucides"}

    @pytest.mark.unit
    def test_calorie_decay_scale_uses_tolerance(self, builder) -> None:
        q = builder.build(_targets(), [], "standard", [])
        cal_fn = next(fn for fn in _functions(q) if "calories" in fn.get("gauss", {}))
        # scale = |2000| * 0.10
        assert cal_fn["gauss"]["calories"]["scale"] == pytest.approx(200.0)
        assert cal_fn["gauss"]["calories"]["origin"] == 2000

    @pytest.mark.unit
    def test_decay_functions_filtered_on_exists(self, builder) -> None:
        """Les recettes sans macro renseignée ne sont pas scorées (filtre exists)."""
        q = builder.build(_targets(), [], "standard", [])
        for fn in _functions(q):
            if "gauss" in fn:
                field = next(iter(fn["gauss"]))
                assert fn["filter"] == {"exists": {"field": field}}
