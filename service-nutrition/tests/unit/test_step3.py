"""Tests Étape 3 — critères de recherche de recettes & scoring."""

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


class TestSearchQueryBuilder:
    @pytest.mark.unit
    def test_exclusions_terms_and_diet_tags(self, builder) -> None:
        """Aliments exclus → termes ; régime vegan → tags."""
        c = builder.build(_targets(), ["arachide", "lactose"], "vegan")
        assert "arachide" in c.excluded_terms
        assert "lactose" in c.excluded_terms
        assert "gelatine" in c.excluded_terms  # pas de tag gélatine → par nom
        assert "enums.type_of_ingredient.meat" in c.excluded_tags
        assert "enums.type_of_ingredient.egg" in c.excluded_tags

    @pytest.mark.unit
    def test_halal_bans_pork_by_name_and_alcohol_by_tag(self, builder) -> None:
        c = builder.build(_targets(), [], "halal")
        assert "porc" in c.excluded_terms
        assert "enums.type_of_ingredient.alcohol" in c.excluded_tags

    @pytest.mark.unit
    def test_standard_diet_has_no_diet_ban(self, builder) -> None:
        c = builder.build(_targets(), [], "standard")
        assert c.excluded_tags == []
        assert c.excluded_terms == []

    @pytest.mark.unit
    def test_exclusions_deduplicated_and_blank_dropped(self, builder) -> None:
        c = builder.build(_targets(), ["porc", " ", "porc"], "no_pork")
        assert c.excluded_terms.count("porc") == 1
        assert "" not in c.excluded_terms

    @pytest.mark.unit
    def test_strict_priority_becomes_required_field(self, builder) -> None:
        fps = [FilterPriority(field_name="cooking_time", is_strict=True)]
        c = builder.build(_targets(fps), [], "standard")
        assert c.required_fields == ["cooking_time"]
        # ...et jamais en scoring
        assert all(p.field != "cooking_time" for p in c.preferences)

    @pytest.mark.unit
    def test_soft_priority_becomes_scoring_only(self, builder) -> None:
        fps = [FilterPriority(field_name="budget", is_strict=False, ui_weight=2.0)]
        c = builder.build(_targets(fps), [], "standard")
        assert c.required_fields == []
        assert [(p.field, p.weight) for p in c.preferences] == [("budget", 2.0)]

    @pytest.mark.unit
    def test_macro_targets_present(self, builder) -> None:
        """4 cibles de proximité : calories + 3 macros."""
        c = builder.build(_targets(), [], "standard")
        assert {m.field for m in c.macro_targets} == {
            "calories",
            "proteines",
            "lipides",
            "glucides",
        }

    @pytest.mark.unit
    def test_scale_uses_tolerances(self, builder) -> None:
        c = builder.build(_targets(), [], "standard")
        by_field = {m.field: m for m in c.macro_targets}
        # calories : |2000| × 0.10 ; macros : |160| × 0.15
        assert by_field["calories"].target == 2000
        assert by_field["calories"].scale == pytest.approx(200.0)
        assert by_field["proteines"].scale == pytest.approx(24.0)

    @pytest.mark.unit
    def test_missing_macro_not_scored(self, builder) -> None:
        """L'appareil peut n'envoyer que les calories : pas de cible macro inventée."""
        targets = _targets().model_copy(update={"lipides": None, "glucides": None})
        c = builder.build(targets, [], "standard")
        assert {m.field for m in c.macro_targets} == {"calories", "proteines"}
