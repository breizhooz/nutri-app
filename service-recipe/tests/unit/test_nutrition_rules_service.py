from unittest.mock import AsyncMock

from app.core.config import settings
from app.core.http_client import NutritionTargetsResult
from app.schemas.nutrition_summary import NutritionSummary
from app.schemas.search import MacroTarget, SearchCriteria
from app.services.nutrition_rules_service import NutritionRulesService

ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _summary(
    rules_enabled=True,
    with_targets=True,
    variety=0.10,
    override_calories=None,
) -> NutritionSummary:
    return NutritionSummary.model_validate(
        {
            "account_id": ACCOUNT_ID,
            "main_goal": "weight_loss",
            "diet_type": "vegetarian",
            "excluded_foods": ["arachide", "sucre"],
            "targets": (
                {"calories": 2000, "proteines": 150, "glucides": 200, "lipides": 60}
                if with_targets
                else None
            ),
            "rules": {
                "enabled": rules_enabled,
                "variety_pct": variety,
                "override_calories": override_calories,
                "override_proteines": None,
            },
        }
    )


_CRITERIA = SearchCriteria(
    excluded_terms=["porc"],
    required_fields=["course_type"],
    macro_targets=[MacroTarget(field="calories", target=2000, scale=200)],
)


def _engine_result():
    return NutritionTargetsResult(
        targets={"calories": 2000.0, "warnings": ["w"]},
        search_criteria=_CRITERIA,
    )


def _make_service(summary=None, engine=None):
    profile = AsyncMock()
    profile.get_nutrition_summary = AsyncMock(return_value=summary)
    nutrition = AsyncMock()
    nutrition.compute_targets = AsyncMock(return_value=engine)
    search = AsyncMock()
    search.search_recipes = AsyncMock(return_value={"total": 0, "results": []})
    svc = NutritionRulesService(
        search, profile_client=profile, nutrition_client=nutrition
    )
    return svc, profile, nutrition, search


class TestNutritionRulesService:
    async def test_apply_rules_false_skips_profile(self):
        svc, profile, nutrition, search = _make_service()
        await svc.search(
            account_id=ACCOUNT_ID, apply_rules=False, query="poulet", limit=5
        )
        profile.get_nutrition_summary.assert_not_called()
        nutrition.compute_targets.assert_not_called()
        search.search_recipes.assert_awaited_once()
        assert search.search_recipes.call_args.kwargs["query"] == "poulet"

    async def test_profile_resolved_by_active_account(self):
        svc, profile, _, _ = _make_service(summary=None)
        await svc.search(account_id=ACCOUNT_ID)
        (account,), _ = profile.get_nutrition_summary.call_args
        assert str(account) == ACCOUNT_ID

    async def test_no_summary_falls_back_to_standard(self):
        svc, _, nutrition, search = _make_service(summary=None)
        await svc.search(account_id=ACCOUNT_ID)
        nutrition.compute_targets.assert_not_called()
        assert "criteria" not in search.search_recipes.call_args.kwargs

    async def test_rules_disabled_falls_back(self):
        svc, _, nutrition, _ = _make_service(summary=_summary(rules_enabled=False))
        await svc.search(account_id=ACCOUNT_ID)
        nutrition.compute_targets.assert_not_called()

    async def test_no_targets_yet_falls_back(self):
        """Tant que l'appareil n'a pas envoyé de cibles, recherche standard."""
        svc, _, nutrition, _ = _make_service(summary=_summary(with_targets=False))
        await svc.search(account_id=ACCOUNT_ID)
        nutrition.compute_targets.assert_not_called()

    async def test_engine_none_falls_back(self):
        svc, _, nutrition, search = _make_service(summary=_summary(), engine=None)
        await svc.search(account_id=ACCOUNT_ID)
        nutrition.compute_targets.assert_awaited_once()
        assert "criteria" not in search.search_recipes.call_args.kwargs

    async def test_full_path_passes_device_targets_and_criteria(self, monkeypatch):
        monkeypatch.setattr(settings, "APPLY_NUTRITION_SCORING", False)
        svc, _, nutrition, search = _make_service(
            summary=_summary(), engine=_engine_result()
        )
        out = await svc.search(account_id=ACCOUNT_ID, query="curry")

        eng_kwargs = nutrition.compute_targets.call_args.kwargs
        assert eng_kwargs["diet_type"] == "vegetarian"
        assert eng_kwargs["targets"] == {
            "calories": 2000,
            "proteines": 150,
            "glucides": 200,
            "lipides": 60,
        }
        assert eng_kwargs["excluded_foods"] == ["arachide", "sucre"]
        # aucune donnée corporelle ou médicale transmise au moteur
        assert not {"tdee_kcal", "bmr_kcal", "weight_kg"} & set(eng_kwargs)

        kw = search.search_recipes.call_args.kwargs
        assert kw["criteria"] == _CRITERIA
        assert kw["apply_scoring"] is False
        assert out["nutrition_targets"]["warnings"] == ["w"]

    async def test_saved_defaults_applied_when_no_cursors(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(variety=0.2, override_calories=1800),
            engine=_engine_result(),
        )
        await svc.search(account_id=ACCOUNT_ID)
        adj = nutrition.compute_targets.call_args.kwargs["adjustment"]
        assert adj["manual_calories_override"] == 1800
        assert adj["tolerances"] == {"calories_pct": 0.2, "macros_pct": 0.25}

    async def test_live_cursor_overrides_saved_default(self):
        svc, _, nutrition, _ = _make_service(
            summary=_summary(variety=0.2), engine=_engine_result()
        )
        await svc.search(account_id=ACCOUNT_ID, variety_pct=0.3, override_proteines=170)
        adj = nutrition.compute_targets.call_args.kwargs["adjustment"]
        assert adj["tolerances"]["calories_pct"] == 0.3
        assert adj["manual_proteines_override"] == 170

    async def test_scoring_enabled_by_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "APPLY_NUTRITION_SCORING", True)
        svc, _, _, search = _make_service(summary=_summary(), engine=_engine_result())
        await svc.search(account_id=ACCOUNT_ID)
        kw = search.search_recipes.call_args.kwargs
        assert kw["apply_scoring"] is True
        assert kw["criteria"].macro_targets[0].target == 2000
