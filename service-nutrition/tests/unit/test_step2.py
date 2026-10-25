"""Tests Étape 2 — ajustements UI sur les cibles reçues de l'appareil."""

import pytest

from app.schemas.engine import (
    DailyTargets,
    FilterPriority,
    TargetTolerance,
    UserAdjustmentProfile,
)
from app.services.engine.step2_user_overrides import UserOverridesService


@pytest.fixture
def service() -> UserOverridesService:
    return UserOverridesService()


@pytest.fixture
def targets() -> DailyTargets:
    return DailyTargets(calories=2000, proteines=160, lipides=55.6, glucides=215)


class TestUserOverridesService:
    @pytest.mark.unit
    def test_targets_passed_through(self, service, targets) -> None:
        final = service.apply(targets, UserAdjustmentProfile())
        assert (final.calories, final.proteines, final.lipides, final.glucides) == (
            2000,
            160,
            55.6,
            215,
        )
        assert final.warnings == []

    @pytest.mark.unit
    def test_manual_overrides_win(self, service, targets) -> None:
        final = service.apply(
            targets,
            UserAdjustmentProfile(
                manual_calories_override=1800, manual_proteines_override=150
            ),
        )
        assert final.calories == 1800
        assert final.proteines == 150
        # lipides/glucides jamais recalculés
        assert final.lipides == 55.6

    @pytest.mark.unit
    def test_missing_macros_stay_missing(self, service) -> None:
        final = service.apply(DailyTargets(calories=2200), UserAdjustmentProfile())
        assert final.calories == 2200
        assert final.proteines is None and final.lipides is None

    @pytest.mark.unit
    def test_metadata_propagated(self, service, targets) -> None:
        tol = TargetTolerance(calories_pct=0.2, macros_pct=0.25)
        fps = [FilterPriority(field_name="cooking_time", is_strict=True)]
        final = service.apply(
            targets, UserAdjustmentProfile(tolerances=tol, filter_priorities=fps)
        )
        assert final.tolerances == tol
        assert final.filter_priorities == fps
