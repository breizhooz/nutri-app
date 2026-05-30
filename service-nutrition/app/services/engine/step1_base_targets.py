"""Étape 1 — Noyau mathématique des cibles nutritionnelles.

Fonctions pures : aucune I/O, aucun état global, aucun appel DB.
Ne connaît PAS le profil utilisateur (UserAdjustmentProfile) — cf. Règle d'or 1.
"""

from app.schemas.engine import BaseTargets

# Calories par gramme de macronutriment.
_KCAL_PER_G_PROT = 4.0
_KCAL_PER_G_GLUC = 4.0
_KCAL_PER_G_LIPID = 9.0

# Profil macros standard par objectif : (protéines g/kg, part lipides en % des kcal).
_MACRO_PROFILE: dict[str, tuple[float, float]] = {
    "weight_loss": (2.0, 0.25),
    "muscle_gain": (1.8, 0.20),
    "body_recomposition": (2.2, 0.25),
    "sports_performance": (1.6, 0.30),
    "maintenance": (1.4, 0.30),
}

# Règle spéciale keto.
_KETO_GLUCIDES_G = 30.0
_KETO_PROT_G_PER_KG = 1.5

# Plancher glucides pour la performance sportive.
_SPORTS_MIN_GLUC_G_PER_KG = 4.0


class BaseTargetsCalculator:
    """Calcule les cibles théoriques pures à partir des seules données physiologiques."""

    def calculate(
        self,
        goal: str,
        diet_type: str,
        tdee_kcal: float,
        bmr_kcal: float,
        weight_kg: float,
    ) -> BaseTargets:
        """Retourne les cibles de base (calories + macros) pour un objectif donné.

        Cascade de calcul : calories → protéines → lipides → glucides.
        Lève ``ValueError`` si ``goal`` est inconnu.
        """
        calories = self._calories_for_goal(goal, tdee_kcal, bmr_kcal)

        if diet_type == "keto":
            proteines, lipides, glucides = self._macros_keto(calories, weight_kg)
        else:
            proteines, lipides, glucides = self._macros_standard(
                goal, calories, weight_kg
            )

        # Arrondi uniquement en sortie (précision intermédiaire conservée).
        return BaseTargets(
            calories=round(calories, 1),
            proteines=round(proteines, 1),
            lipides=round(lipides, 1),
            glucides=round(glucides, 1),
        )

    @staticmethod
    def _calories_for_goal(goal: str, tdee_kcal: float, bmr_kcal: float) -> float:
        """Calories cibles selon l'objectif. ``max(…, bmr+100)`` = garde-fou absolu."""
        match goal:
            case "weight_loss":
                return max(tdee_kcal * 0.80, bmr_kcal + 100)
            case "muscle_gain":
                return tdee_kcal * 1.12
            case "body_recomposition":
                return tdee_kcal * 0.95
            case "sports_performance":
                return tdee_kcal
            case "maintenance":
                return tdee_kcal
            case _:
                raise ValueError(f"Objectif nutritionnel inconnu : {goal!r}")

    @staticmethod
    def _macros_standard(
        goal: str, calories: float, weight_kg: float
    ) -> tuple[float, float, float]:
        """Macros standard : protéines g/kg, lipides en % kcal, glucides = reste."""
        prot_per_kg, lipid_pct = _MACRO_PROFILE[goal]

        proteines = prot_per_kg * weight_kg
        lipides = (calories * lipid_pct) / _KCAL_PER_G_LIPID
        glucides = (
            calories - proteines * _KCAL_PER_G_PROT - lipides * _KCAL_PER_G_LIPID
        ) / _KCAL_PER_G_GLUC

        if goal == "sports_performance":
            glucides = max(glucides, _SPORTS_MIN_GLUC_G_PER_KG * weight_kg)

        return proteines, lipides, glucides

    @staticmethod
    def _macros_keto(calories: float, weight_kg: float) -> tuple[float, float, float]:
        """Macros keto : glucides fixes (30 g), protéines 1.5 g/kg, lipides = reste."""
        proteines = _KETO_PROT_G_PER_KG * weight_kg
        glucides = _KETO_GLUCIDES_G
        lipides = (
            calories - proteines * _KCAL_PER_G_PROT - glucides * _KCAL_PER_G_GLUC
        ) / _KCAL_PER_G_LIPID
        return proteines, lipides, glucides
