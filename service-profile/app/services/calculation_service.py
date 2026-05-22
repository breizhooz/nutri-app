"""Service de calcul métabolique — BMR, TDEE, IMC, macronutriments, poids idéal."""

import logging
from datetime import date, datetime, timezone

from app.i18n import t
from app.models.enums import ActivityLevel, BiologicalSex, MainGoal
from app.models.lifestyle_profile import LifestyleProfile
from app.models.nutrition_preferences import NutritionPreferences
from app.models.profile import Profile
from app.models.sports_profile import SportsProfile
from app.schemas.calculations import CalculationResponse, MacrosResponse

logger = logging.getLogger(__name__)


class CalculationService:
    """Calculs métaboliques basés sur les formules Mifflin-St Jeor et Devine.

    Toutes les données constantes sont des attributs de classe.
    Aucune dépendance externe ou base de données.
    """

    _PROFESSION_PAL: dict[ActivityLevel, float] = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHT: 1.375,
        ActivityLevel.MODERATE: 1.55,
        ActivityLevel.HEAVY: 1.725,
        ActivityLevel.VERY_HEAVY: 1.9,
    }

    _BMI_THRESHOLDS: list[tuple[float, str]] = [
        (16.0, "bmi_category.severe_malnutrition"),
        (17.0, "bmi_category.moderate_malnutrition"),
        (18.5, "bmi_category.underweight"),
        (25.0, "bmi_category.normal"),
        (30.0, "bmi_category.overweight"),
        (35.0, "bmi_category.moderate_obesity"),
        (40.0, "bmi_category.severe_obesity"),
        (float("inf"), "bmi_category.morbid_obesity"),
    ]

    _MACRO_SPLITS: dict[MainGoal, tuple[float, float, float]] = {
        MainGoal.WEIGHT_LOSS: (0.40, 0.30, 0.30),
        MainGoal.MUSCLE_GAIN: (0.40, 0.35, 0.25),
        MainGoal.BODY_RECOMPOSITION: (0.40, 0.30, 0.30),
        MainGoal.SPORTS_PERFORMANCE: (0.50, 0.25, 0.25),
        MainGoal.MAINTENANCE: (0.45, 0.25, 0.30),
    }

    def compute_age(self, dob: date) -> int:
        """Calcule l'âge exact en années à partir de la date de naissance."""
        today = datetime.now(timezone.utc).date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def compute_bmr(
        self, weight_kg: float, height_cm: float, age: int, sex: BiologicalSex
    ) -> float:
        """Calcule le métabolisme de base via la formule Mifflin-St Jeor.

        Homme  : 10×poids + 6.25×taille − 5×âge + 5
        Femme  : 10×poids + 6.25×taille − 5×âge − 161
        """
        base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
        return base + 5.0 if sex == BiologicalSex.MALE else base - 161.0

    def compute_bmi(self, weight_kg: float, height_cm: float) -> float:
        """Calcule l'Indice de Masse Corporelle (poids / taille²)."""
        return round(weight_kg / (height_cm / 100.0) ** 2, 1)

    def bmi_category_key(self, bmi: float) -> str:
        """Retourne la clé i18n de la catégorie IMC correspondante."""
        for threshold, key in self._BMI_THRESHOLDS:
            if bmi < threshold:
                return key
        return "bmi_category.morbid_obesity"

    def compute_pal(
        self, lifestyle: LifestyleProfile, sports: SportsProfile | None
    ) -> float:
        """Calcule le coefficient d'activité physique (PAL) combiné profession + sport.

        Bonus sport : 0.025 par séance/semaine, pondéré par l'intensité RPE/5.
        Plafond du bonus sport : 0.3 pour éviter la surestimation.
        """
        base = self._PROFESSION_PAL[lifestyle.profession_activity_level]
        if sports:
            bonus = min(
                sports.sessions_per_week * 0.025 * (sports.avg_intensity_rpe / 5.0), 0.3
            )
        else:
            bonus = 0.0
        return round(base + bonus, 3)

    def compute_ideal_weight(
        self, height_cm: float, sex: BiologicalSex
    ) -> tuple[float, float]:
        """Calcule la fourchette de poids idéal via la formule Devine (±10%).

        Retourne (min_kg, max_kg).
        """
        inches_over_5ft = (height_cm / 2.54) - 60.0
        if sex == BiologicalSex.MALE:
            mid_kg = 50.0 + 2.3 * inches_over_5ft
        else:
            mid_kg = 45.5 + 2.3 * inches_over_5ft
        return round(mid_kg * 0.9, 1), round(mid_kg * 1.1, 1)

    def compute_macros(self, tdee: int, goal: MainGoal) -> MacrosResponse:
        """Calcule la répartition en grammes des macronutriments pour l'objectif donné."""
        carb_r, prot_r, fat_r = self._MACRO_SPLITS[goal]
        prot_kcal = round(tdee * prot_r)
        carb_kcal = round(tdee * carb_r)
        fat_kcal = round(tdee * fat_r)
        return MacrosResponse(
            goal=goal,
            tdee_kcal=tdee,
            proteins_g=prot_kcal // 4,
            carbs_g=carb_kcal // 4,
            fats_g=fat_kcal // 9,
            proteins_kcal=prot_kcal,
            carbs_kcal=carb_kcal,
            fats_kcal=fat_kcal,
        )

    def calculate(
        self,
        profile: Profile,
        lifestyle: LifestyleProfile | None,
        sports: SportsProfile | None,
        nutrition: NutritionPreferences | None,
        locale: str = "fr",
    ) -> CalculationResponse:
        """Calcul métabolique complet : IMC, MB, TDEE, poids idéal, macros.

        Lève ValueError('missing_data_calc') si les données anthropométriques sont incomplètes.
        """
        if not all(
            [
                profile.date_of_birth,
                profile.weight_kg,
                profile.height_cm,
                profile.biological_sex,
            ]
        ):
            logger.warning(
                "Données insuffisantes pour le calcul : profile_id=%s", profile.id
            )
            raise ValueError("missing_data_calc")

        weight = float(profile.weight_kg)  # type: ignore[arg-type]
        height = float(profile.height_cm)  # type: ignore[arg-type]
        age = self.compute_age(profile.date_of_birth)  # type: ignore[arg-type]
        sex: BiologicalSex = profile.biological_sex  # type: ignore[assignment]

        bmi = self.compute_bmi(weight, height)
        bmr = self.compute_bmr(weight, height, age, sex)
        pal = self.compute_pal(lifestyle, sports) if lifestyle else 1.2
        tdee = round(bmr * pal)
        ideal_min, ideal_max = self.compute_ideal_weight(height, sex)
        macros = self.compute_macros(tdee, nutrition.main_goal) if nutrition else None

        logger.debug("Calcul terminé : BMI=%.1f BMR=%d TDEE=%d", bmi, bmr, tdee)
        return CalculationResponse(
            bmi=bmi,
            bmi_category=t.get(self.bmi_category_key(bmi), locale),
            bmr_kcal=round(bmr),
            tdee_kcal=tdee,
            pal=pal,
            ideal_weight_min_kg=ideal_min,
            ideal_weight_max_kg=ideal_max,
            macros=macros,
        )
