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

    # Facteur d'ajustement énergétique par objectif (déficit < 1, surplus > 1).
    # Aligné sur le moteur de ciblage recettes (service-nutrition,
    # engine/step1_base_targets._calories_for_goal) pour que l'objectif affiché à
    # l'utilisateur corresponde aux cibles servant à filtrer les recettes.
    _GOAL_ENERGY_FACTOR: dict[MainGoal, float] = {
        MainGoal.WEIGHT_LOSS: 0.80,
        MainGoal.MUSCLE_GAIN: 1.12,
        MainGoal.BODY_RECOMPOSITION: 0.95,
        MainGoal.SPORTS_PERFORMANCE: 1.0,
        MainGoal.MAINTENANCE: 1.0,
    }

    # Plancher de sécurité : la cible ne descend jamais sous BMR + 100 kcal.
    _CALORIE_FLOOR_OVER_BMR: float = 100.0

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

    def compute_target_calories(
        self, tdee_kcal: float, bmr_kcal: float, goal: MainGoal
    ) -> tuple[int, int, bool]:
        """Cible énergétique quotidienne = TDEE ajusté selon l'objectif.

        Applique un déficit (perte de poids/recomposition), un surplus (prise de
        masse) ou la maintenance, avec un plancher de sécurité à ``BMR + 100``.

        Returns:
            (target_kcal, adjustment_pct signé, floored) où ``floored`` indique
            que le plancher de sécurité a écrasé l'ajustement nominal.
        """
        factor = self._GOAL_ENERGY_FACTOR[goal]
        raw = tdee_kcal * factor
        floor = bmr_kcal + self._CALORIE_FLOOR_OVER_BMR
        floored = raw < floor
        target = floor if floored else raw
        return round(target), round((factor - 1.0) * 100), floored

    def compute_macros(self, target_kcal: int, goal: MainGoal) -> MacrosResponse:
        """Répartit les calories **cibles** (après déficit/surplus) en grammes de macros."""
        carb_r, prot_r, fat_r = self._MACRO_SPLITS[goal]
        prot_kcal = round(target_kcal * prot_r)
        carb_kcal = round(target_kcal * carb_r)
        fat_kcal = round(target_kcal * fat_r)
        return MacrosResponse(
            goal=goal,
            tdee_kcal=target_kcal,
            proteins_g=prot_kcal // 4,
            carbs_g=carb_kcal // 4,
            fats_g=fat_kcal // 9,
            proteins_kcal=prot_kcal,
            carbs_kcal=carb_kcal,
            fats_kcal=fat_kcal,
        )

    def build_objective_explanation(
        self,
        *,
        bmr_kcal: int,
        pal: float,
        tdee_kcal: int,
        bmi: float,
        bmi_category: str,
        ideal_min: float,
        ideal_max: float,
        macros: MacrosResponse | None,
        goal: MainGoal | None,
        target_calories: int | None = None,
        adjustment_pct: int = 0,
        floored: bool = False,
        locale: str = "fr",
    ) -> str:
        """Construit une explication textuelle déterministe de l'objectif calculé.

        Assemble des phrases i18n paramétrées (aucun LLM) à partir des valeurs déjà
        calculées. Les phrases d'objectif, de cible énergétique (déficit/surplus)
        et de macros ne sont incluses que si l'objectif nutritionnel est connu.
        """
        parts: list[str] = []
        if goal is not None:
            parts.append(
                t.get(
                    "objective_explanation.goal",
                    locale,
                    goal=t.get(f"main_goal.{goal.value}", locale),
                )
            )
        parts.append(
            t.get(
                "objective_explanation.energy",
                locale,
                bmr=bmr_kcal,
                pal=f"{pal:g}",
                tdee=tdee_kcal,
            )
        )
        if target_calories is not None:
            if adjustment_pct < 0:
                key = "objective_explanation.target_deficit"
            elif adjustment_pct > 0:
                key = "objective_explanation.target_surplus"
            else:
                key = "objective_explanation.target_maintenance"
            parts.append(
                t.get(
                    key,
                    locale,
                    pct=abs(adjustment_pct),
                    target=target_calories,
                    tdee=tdee_kcal,
                )
            )
            if floored:
                parts.append(
                    t.get(
                        "objective_explanation.target_floored",
                        locale,
                        target=target_calories,
                    )
                )
        if macros is not None:
            parts.append(
                t.get(
                    "objective_explanation.macros",
                    locale,
                    proteins_g=macros.proteins_g,
                    carbs_g=macros.carbs_g,
                    fats_g=macros.fats_g,
                )
            )
        parts.append(
            t.get(
                "objective_explanation.bmi",
                locale,
                bmi=f"{bmi:.1f}",
                bmi_category=bmi_category,
                ideal_min=f"{ideal_min:.1f}",
                ideal_max=f"{ideal_max:.1f}",
            )
        )
        return " ".join(parts)

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

        # Cible énergétique = TDEE ajusté du déficit/surplus de l'objectif ; les
        # macros sont réparties sur cette cible (et non sur la maintenance brute).
        target_calories: int | None = None
        adjustment_pct = 0
        floored = False
        macros = None
        if nutrition:
            target_calories, adjustment_pct, floored = self.compute_target_calories(
                tdee, bmr, nutrition.main_goal
            )
            macros = self.compute_macros(target_calories, nutrition.main_goal)

        bmi_category = t.get(self.bmi_category_key(bmi), locale)
        explanation = self.build_objective_explanation(
            bmr_kcal=round(bmr),
            pal=pal,
            tdee_kcal=tdee,
            bmi=bmi,
            bmi_category=bmi_category,
            ideal_min=ideal_min,
            ideal_max=ideal_max,
            macros=macros,
            goal=nutrition.main_goal if nutrition else None,
            target_calories=target_calories,
            adjustment_pct=adjustment_pct,
            floored=floored,
            locale=locale,
        )

        logger.debug(
            "Calcul terminé : BMI=%.1f BMR=%d TDEE=%d cible=%s",
            bmi,
            bmr,
            tdee,
            target_calories,
        )
        return CalculationResponse(
            bmi=bmi,
            bmi_category=bmi_category,
            bmr_kcal=round(bmr),
            tdee_kcal=tdee,
            pal=pal,
            ideal_weight_min_kg=ideal_min,
            ideal_weight_max_kg=ideal_max,
            macros=macros,
            target_calories_kcal=target_calories,
            energy_adjustment_pct=adjustment_pct,
            explanation=explanation,
        )
