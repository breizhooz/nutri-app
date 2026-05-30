"""Tests Étape 2 — ajustement utilisateur & garde-fous de sécurité."""

import pytest

from app.schemas.engine import (
    BaseTargets,
    FilterPriority,
    TargetTolerance,
    UserAdjustmentProfile,
)
from app.services.engine.step2_user_overrides import UserOverridesService


@pytest.fixture
def service() -> UserOverridesService:
    return UserOverridesService()


@pytest.fixture
def base() -> BaseTargets:
    return BaseTargets(calories=2000, proteines=160, lipides=55.6, glucides=215)


class TestUserOverrides:
    @pytest.mark.unit
    def test_nominal_no_override(self, service, base) -> None:
        """Sans override ni agressivité : on retombe sur les calories de base."""
        out = service.apply(base, UserAdjustmentProfile(), "weight_loss", 2500, 1700, 80)
        assert out.calories == 2000.0  # 2500 - (2500-2000)*1.0
        assert out.proteines == 160.0
        assert out.lipides == 55.6  # repris de la base (pas recalculé)
        assert out.glucides == 215.0
        assert out.warnings == []

    @pytest.mark.unit
    def test_aggressiveness_intense_hits_floor(self, service, base) -> None:
        """Agressivité intense pousse sous le plancher BMR+100 → corrigé + warning."""
        profile = UserAdjustmentProfile(aggressiveness_factor=1.5)
        out = service.apply(base, profile, "weight_loss", 2500, 1700, 80)
        # 2500 - 500*1.5 = 1750 < 1800 → plancher
        assert out.calories == 1800.0
        assert len(out.warnings) == 1

    @pytest.mark.unit
    def test_manual_calories_override_respected(self, service, base) -> None:
        profile = UserAdjustmentProfile(manual_calories_override=2300)
        out = service.apply(base, profile, "weight_loss", 2500, 1700, 80)
        assert out.calories == 2300.0
        assert out.warnings == []

    @pytest.mark.unit
    def test_manual_calories_override_below_floor_refused(self, service, base) -> None:
        """Le plancher s'applique MÊME sur un override manuel."""
        profile = UserAdjustmentProfile(manual_calories_override=1200)
        out = service.apply(base, profile, "weight_loss", 2500, 1700, 80)
        assert out.calories == 1800.0  # bmr+100
        assert any("plancher" in w.lower() for w in out.warnings)

    @pytest.mark.unit
    def test_manual_proteines_override_capped(self, service, base) -> None:
        """Plafond protéines = poids × 3.5 g/kg, même sur override."""
        profile = UserAdjustmentProfile(manual_proteines_override=400)
        out = service.apply(base, profile, "muscle_gain", 2500, 1700, 80)
        assert out.proteines == 280.0  # 80 * 3.5
        assert any("protéines" in w.lower() for w in out.warnings)

    @pytest.mark.unit
    def test_manual_proteines_override_within_cap(self, service, base) -> None:
        profile = UserAdjustmentProfile(manual_proteines_override=180)
        out = service.apply(base, profile, "muscle_gain", 2500, 1700, 80)
        assert out.proteines == 180.0
        assert out.warnings == []

    @pytest.mark.unit
    def test_metadata_propagated(self, service, base) -> None:
        """Tolérances et priorités de filtre sont propagées telles quelles."""
        tol = TargetTolerance(calories_pct=0.05, macros_pct=0.20)
        fps = [FilterPriority(field_name="budget", is_strict=True, ui_weight=2.0)]
        profile = UserAdjustmentProfile(tolerances=tol, filter_priorities=fps)
        out = service.apply(base, profile, "maintenance", 2200, 1600, 70)
        assert out.tolerances == tol
        assert out.filter_priorities == fps
