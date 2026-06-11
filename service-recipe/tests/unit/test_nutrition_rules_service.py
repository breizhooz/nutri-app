from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.config import settings
from app.core.http_client import NutritionTargetsResult
from app.services.nutrition_rules_service import NutritionRulesService

USER_ID = "00000000-0000-0000-0000-000000000001"


def _summary(
    rules_enabled=True,
    with_calc=True,
    with_prefs=True,
    weight=80.0,
    rules_aggr=1.0,
    rules_var=0.10,
):
    return SimpleNamespace(
        profile=SimpleNamespace(
            nutrition_rules_enabled=rules_enabled, weight_kg=weight
        ),
        calculation=(
            SimpleNamespace(tdee_kcal=2500, bmr_kcal=1700) if with_calc else None
        ),
        nutrition_preferences=(
            SimpleNamespace(
                main_goal="weight_loss",
                diet_type="standard",
                excluded_foods=["sucre"],
                rules_aggressiveness=rules_aggr,
                rules_variety_pct=rules_var,
                rules_override_calories=None,
                rules_override_proteines=None,
            )
            if with_prefs
            else None
        ),
        allergies=[SimpleNamespace(allergen="gluten")],
        excluded_foods=[SimpleNamespace(food_name="arachide")],
    )


def _engine_result():
    return NutritionTargetsResult(
        targets={"calories": 2000.0, "warnings": ["w"]},
        search_query={
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "must_not": [{"terms": {"ingredient_names": ["porc"]}}],
                            "filter": [{"exists": {"field": "course_type"}}],
                        }
                    },
                    "functions": [
                        {"gauss": {"calories": {"origin": 2000, "scale": 200}}}
                    ],
                }
            }
        },
    )


def _make_service(summary=None, engine=None):
    profile = AsyncMock()
    profile.get_nutrition_summary = AsyncMock(return_value=summary)
    nutrition = AsyncMock()
    nutrition.compute_targets = AsyncMock(return_value=engine)
    search = AsyncMock()
    search.search_recipes = AsyncMock(return_value={"total": 0, "results": []})
    svc = NutritionRulesService(
        profile_client=profile, nutrition_client=nutrition, search=search
    )
    return svc, profile, nutrition, search


class TestNutritionRulesService:
    async def test_apply_rules_false_skips_profile(self):
        svc, profile, nutrition, search = _make_service()
        await svc.search(user_id=USER_ID, account_id=USER_ID, apply_rules=False, query="poulet", limit=5)
        profile.get_nutrition_summary.assert_not_called()
        nutrition.compute_targets.assert_not_called()
        search.search_recipes.assert_awaited_once()
        assert search.search_recipes.call_args.kwargs["query"] == "poulet"

    async def test_no_summary_falls_back_to_standard(self):
        svc, _, nutrition, search = _make_service(summary=None)
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        nutrition.compute_targets.assert_not_called()
        assert "extra_must_not" not in search.search_recipes.call_args.kwargs

    async def test_rules_disabled_falls_back(self):
        svc, _, nutrition, search = _make_service(summary=_summary(rules_enabled=False))
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        nutrition.compute_targets.assert_not_called()
        assert "extra_must_not" not in search.search_recipes.call_args.kwargs

    async def test_missing_calculation_falls_back(self):
        svc, _, nutrition, search = _make_service(summary=_summary(with_calc=False))
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        nutrition.compute_targets.assert_not_called()

    async def test_engine_none_falls_back(self):
        svc, _, nutrition, search = _make_service(summary=_summary(), engine=None)
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        nutrition.compute_targets.assert_awaited_once()
        assert "extra_must_not" not in search.search_recipes.call_args.kwargs

    async def test_full_path_merges_clauses(self, monkeypatch):
        monkeypatch.setattr(settings, "APPLY_NUTRITION_SCORING", False)
        svc, _, nutrition, search = _make_service(
            summary=_summary(), engine=_engine_result()
        )
        out = await svc.search(user_id=USER_ID, account_id=USER_ID, query="curry")

        # entrées du moteur dérivées du résumé
        eng_kwargs = nutrition.compute_targets.call_args.kwargs
        assert eng_kwargs["goal"] == "weight_loss"
        assert eng_kwargs["tdee_kcal"] == 2500
        assert eng_kwargs["weight_kg"] == 80.0
        assert "sucre" in eng_kwargs["excluded_foods"]  # depuis prefs
        assert (
            "arachide" in eng_kwargs["excluded_foods"]
        )  # depuis excluded_foods objets
        assert eng_kwargs["medical_contraindications"] == ["gluten"]

        # clauses fusionnées dans la recherche
        kw = search.search_recipes.call_args.kwargs
        assert kw["extra_must_not"] == [{"terms": {"ingredient_names": ["porc"]}}]
        assert kw["extra_filter"] == [{"exists": {"field": "course_type"}}]
        # scoring désactivé par le flag
        assert kw["scoring_functions"] is None
        # cibles + warnings remontés
        assert out["nutrition_targets"]["warnings"] == ["w"]

    async def test_saved_defaults_applied_when_no_cursors(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(rules_aggr=0.5, rules_var=0.2), engine=_engine_result()
        )
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        adj = nutrition.compute_targets.call_args.kwargs["adjustment"]
        assert adj["aggressiveness_factor"] == 0.5
        assert adj["tolerances"] == {"calories_pct": 0.2, "macros_pct": 0.25}

    async def test_live_cursor_overrides_saved_default(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(rules_aggr=0.5), engine=_engine_result()
        )
        await svc.search(user_id=USER_ID, account_id=USER_ID, aggressiveness=1.5)
        adj = nutrition.compute_targets.call_args.kwargs["adjustment"]
        assert adj["aggressiveness_factor"] == 1.5  # live gagne sur le défaut

    async def test_no_prefs_no_cursors_sends_no_adjustment(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(with_calc=True), engine=_engine_result()
        )
        # prefs sans attributs rules_* (simulé via getattr None)
        svc_summary = _summary()
        svc_summary.nutrition_preferences = SimpleNamespace(
            main_goal="weight_loss", diet_type="standard", excluded_foods=[]
        )
        svc._profile.get_nutrition_summary.return_value = svc_summary
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        assert nutrition.compute_targets.call_args.kwargs["adjustment"] is None

    async def test_cursors_build_adjustment(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(), engine=_engine_result()
        )
        await svc.search(
            user_id=USER_ID, account_id=USER_ID,
            aggressiveness=1.5,
            variety_pct=0.2,
            override_calories=2200,
            override_proteines=170,
        )
        adj = nutrition.compute_targets.call_args.kwargs["adjustment"]
        assert adj["aggressiveness_factor"] == 1.5
        assert adj["manual_calories_override"] == 2200
        assert adj["manual_proteines_override"] == 170
        assert adj["tolerances"] == {"calories_pct": 0.2, "macros_pct": 0.25}

    async def test_scoring_enabled_passes_functions(self, monkeypatch):
        monkeypatch.setattr(settings, "APPLY_NUTRITION_SCORING", True)
        svc, _, _, search = _make_service(summary=_summary(), engine=_engine_result())
        await svc.search(user_id=USER_ID, account_id=USER_ID)
        kw = search.search_recipes.call_args.kwargs
        assert kw["scoring_functions"] == [
            {"gauss": {"calories": {"origin": 2000, "scale": 200}}}
        ]
