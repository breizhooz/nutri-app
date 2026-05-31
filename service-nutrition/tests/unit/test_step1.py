"""Tests Étape 1 — noyau mathématique des cibles (fonctions pures)."""

import pytest

from app.services.engine.step1_base_targets import BaseTargetsCalculator


@pytest.fixture
def calc() -> BaseTargetsCalculator:
    return BaseTargetsCalculator()


class TestBaseTargetsCalculator:
    @pytest.mark.unit
    def test_weight_loss_nominal(self, calc: BaseTargetsCalculator) -> None:
        """Perte de poids : déficit 80 %, 2 g/kg protéines, lipides 25 %, glucides reste."""
        t = calc.calculate(
            "weight_loss", "standard", tdee_kcal=2500, bmr_kcal=1700, weight_kg=80
        )
        assert t.calories == 2000.0  # max(2000, 1800)
        assert t.proteines == 160.0  # 2.0 * 80
        assert t.lipides == 55.6  # 2000*0.25/9
        assert t.glucides == 215.0  # (2000-640-500)/4

    @pytest.mark.unit
    def test_muscle_gain_nominal(self, calc: BaseTargetsCalculator) -> None:
        """Prise de masse : surplus 12 %, 1.8 g/kg, lipides 20 %."""
        t = calc.calculate(
            "muscle_gain", "standard", tdee_kcal=2500, bmr_kcal=1700, weight_kg=80
        )
        assert t.calories == 2800.0
        assert t.proteines == 144.0
        assert t.lipides == 62.2
        assert t.glucides == 416.0

    @pytest.mark.unit
    def test_maintenance_and_recomposition(self, calc: BaseTargetsCalculator) -> None:
        assert (
            calc.calculate("maintenance", "standard", 2200, 1600, 70).calories == 2200.0
        )
        assert (
            calc.calculate("body_recomposition", "standard", 2000, 1500, 70).calories
            == 1900.0
        )

    @pytest.mark.unit
    def test_bmr_floor_triggered(self, calc: BaseTargetsCalculator) -> None:
        """Garde-fou physiologique : calories ne descendent jamais sous bmr+100."""
        t = calc.calculate(
            "weight_loss", "standard", tdee_kcal=2000, bmr_kcal=1900, weight_kg=80
        )
        # 2000*0.8 = 1600 < 1900+100 = 2000 → plancher
        assert t.calories == 2000.0

    @pytest.mark.unit
    def test_keto_override(self, calc: BaseTargetsCalculator) -> None:
        """Keto : glucides fixes à 30 g, protéines 1.5 g/kg, lipides = reste."""
        t = calc.calculate(
            "maintenance", "keto", tdee_kcal=2000, bmr_kcal=1500, weight_kg=80
        )
        assert t.calories == 2000.0
        assert t.proteines == 120.0  # 1.5 * 80
        assert t.glucides == 30.0
        assert t.lipides == 155.6  # (2000-480-120)/9

    @pytest.mark.unit
    def test_sports_min_glucides_floor(self, calc: BaseTargetsCalculator) -> None:
        """Performance : glucides plancher à 4 g/kg si le reste est insuffisant."""
        t = calc.calculate(
            "sports_performance",
            "standard",
            tdee_kcal=2000,
            bmr_kcal=1500,
            weight_kg=80,
        )
        # reste = (0.70*2000-512)/4 = 222 < 4*80 = 320 → plancher
        assert t.glucides == 320.0

    @pytest.mark.unit
    def test_unknown_goal_raises(self, calc: BaseTargetsCalculator) -> None:
        with pytest.raises(ValueError):
            calc.calculate("bulking_dirty", "standard", 2500, 1700, 80)
