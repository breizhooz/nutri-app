"""Tests unitaires du CalculationService — calculs purs sans base de données."""
import pytest
from datetime import date
from unittest.mock import patch

from app.models.enums import ActivityLevel, BiologicalSex, MainGoal
from app.models.lifestyle_profile import LifestyleProfile
from app.models.sports_profile import SportsProfile
from app.models.profile import Profile
from app.services.calculation_service import CalculationService


class TestCalculationService:
    """Tests unitaires du CalculationService."""

    @pytest.fixture
    def svc(self) -> CalculationService:
        """Instance fraîche du service de calcul."""
        return CalculationService()

    @pytest.mark.unit
    def test_bmr_male_nominal(self, svc: CalculationService) -> None:
        """BMR homme : formule Mifflin-St Jeor = 10×88.5 + 6.25×181 - 5×34 + 5."""
        result = svc.compute_bmr(88.5, 181.0, 34, BiologicalSex.MALE)
        assert result == pytest.approx(1851.25, abs=1.0)

    @pytest.mark.unit
    def test_bmr_female_nominal(self, svc: CalculationService) -> None:
        """BMR femme : formule Mifflin-St Jeor = 10×65 + 6.25×165 - 5×28 - 161."""
        result = svc.compute_bmr(65.0, 165.0, 28, BiologicalSex.FEMALE)
        assert result == pytest.approx(1380.25, abs=1.0)

    @pytest.mark.unit
    def test_bmi_normal(self, svc: CalculationService) -> None:
        """IMC normal autour de 22.9 pour 70kg/175cm."""
        assert svc.compute_bmi(70.0, 175.0) == pytest.approx(22.9, abs=0.1)

    @pytest.mark.unit
    def test_bmi_category_normal(self, svc: CalculationService) -> None:
        """Catégorie IMC normale entre 18.5 et 25."""
        assert svc.bmi_category_key(22.0) == "bmi_category.normal"

    @pytest.mark.unit
    def test_bmi_category_overweight(self, svc: CalculationService) -> None:
        """Catégorie IMC surpoids entre 25 et 30."""
        assert svc.bmi_category_key(27.0) == "bmi_category.overweight"

    @pytest.mark.unit
    def test_bmi_category_obese(self, svc: CalculationService) -> None:
        """Catégorie IMC obésité modérée entre 30 et 35."""
        assert svc.bmi_category_key(32.0) == "bmi_category.moderate_obesity"

    @pytest.mark.unit
    def test_pal_sedentary_no_sport(self, svc: CalculationService) -> None:
        """PAL sédentaire sans sport = 1.2."""
        lifestyle = LifestyleProfile(profession_activity_level=ActivityLevel.SEDENTARY)
        assert svc.compute_pal(lifestyle, None) == pytest.approx(1.2)

    @pytest.mark.unit
    def test_pal_increases_with_sport(self, svc: CalculationService) -> None:
        """PAL augmente avec les séances sportives."""
        lifestyle = LifestyleProfile(profession_activity_level=ActivityLevel.SEDENTARY)
        sports = SportsProfile(sessions_per_week=4, avg_intensity_rpe=7)
        assert svc.compute_pal(lifestyle, sports) > 1.2

    @pytest.mark.unit
    def test_pal_sport_bonus_capped(self, svc: CalculationService) -> None:
        """Le bonus sport ne dépasse pas 0.3 même avec 7 séances intenses."""
        lifestyle = LifestyleProfile(profession_activity_level=ActivityLevel.SEDENTARY)
        sports = SportsProfile(sessions_per_week=7, avg_intensity_rpe=10)
        assert svc.compute_pal(lifestyle, sports) <= 1.2 + 0.3 + 0.001

    @pytest.mark.unit
    def test_ideal_weight_male_range(self, svc: CalculationService) -> None:
        """Poids idéal homme 181cm doit être entre 68 et 90 kg."""
        low, high = svc.compute_ideal_weight(181.0, BiologicalSex.MALE)
        assert 68.0 < low < 80.0
        assert 80.0 < high < 95.0

    @pytest.mark.unit
    def test_macros_kcal_sum(self, svc: CalculationService) -> None:
        """La somme des kcal macros doit être proche du TDEE."""
        macros = svc.compute_macros(2500, MainGoal.MAINTENANCE)
        total = macros.proteins_kcal + macros.carbs_kcal + macros.fats_kcal
        assert total == pytest.approx(2500, abs=15)

    @pytest.mark.unit
    def test_calculate_raises_on_missing_weight(self, svc: CalculationService) -> None:
        """ValueError si les données anthropométriques sont incomplètes."""
        profile = Profile(user_id=None, slug="test", weight_kg=None, height_cm=None)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="missing_data_calc"):
            svc.calculate(profile, None, None, None)

    @pytest.mark.unit
    def test_calculate_full_pipeline(self, svc: CalculationService) -> None:
        """Calcul complet retourne un CalculationResponse cohérent."""
        from decimal import Decimal
        import uuid
        profile = Profile(
            id=uuid.uuid4(), user_id=uuid.uuid4(), slug="test",
            date_of_birth=date(1992, 3, 15),
            biological_sex=BiologicalSex.MALE,
            height_cm=Decimal("181.0"),
            weight_kg=Decimal("88.5"),
        )
        result = svc.calculate(profile, None, None, None)
        assert result.bmi == pytest.approx(27.0, abs=0.5)
        assert result.bmr_kcal > 1800
        assert result.tdee_kcal > result.bmr_kcal
        assert result.macros is None