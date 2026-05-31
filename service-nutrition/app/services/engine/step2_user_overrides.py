"""Étape 2 — Couche d'ajustement & sécurité.

Fusionne les cibles de base (Étape 1) avec le profil utilisateur, puis applique
des garde-fous physiologiques NON optionnels (même contre un override manuel).

Ne ré-exécute jamais la cascade macros de l'Étape 1 (cf. Règle d'or 1) : les
lipides et glucides sont repris tels quels des ``BaseTargets``.
"""

import logging

from app.schemas.engine import BaseTargets, FinalTargets, UserAdjustmentProfile

logger = logging.getLogger(__name__)

# Garde-fous de sécurité.
_ABSOLUTE_MIN_CALORIES_OVER_BMR = 100.0  # plancher = bmr + 100
_MAX_PROTEINES_G_PER_KG = 3.5  # plafond néphro-protecteur

_WARN_CALORIES_FLOOR = (
    "Override manuel refusé — plancher physiologique BMR+100 appliqué "
    "({attempted:.0f} kcal → {floor:.0f} kcal)"
)
_WARN_PROTEINES_CAP = (
    "Protéines plafonnées — limite de sécurité {cap:.0f} g appliquée "
    "({attempted:.0f} g → {cap:.0f} g)"
)


class UserOverridesService:
    """Applique les overrides UI puis les garde-fous de sécurité sur les cibles."""

    def apply(
        self,
        base: BaseTargets,
        profile: UserAdjustmentProfile,
        goal: str,
        tdee_kcal: float,
        bmr_kcal: float,
        weight_kg: float,
    ) -> FinalTargets:
        """Fusionne profil + base et sécurise le résultat. Remonte des ``warnings``."""
        warnings: list[str] = []

        final_calories = self._resolve_calories(base, profile, tdee_kcal)
        final_proteines = self._resolve_proteines(base, profile)

        final_calories = self._enforce_calorie_floor(final_calories, bmr_kcal, warnings)
        final_proteines = self._enforce_proteines_cap(
            final_proteines, weight_kg, warnings
        )

        return FinalTargets(
            calories=round(final_calories, 1),
            proteines=round(final_proteines, 1),
            # Décou­plage : lipides/glucides repris de l'Étape 1, jamais recalculés ici.
            lipides=round(base.lipides, 1),
            glucides=round(base.glucides, 1),
            tolerances=profile.tolerances,
            filter_priorities=profile.filter_priorities,
            warnings=warnings,
        )

    @staticmethod
    def _resolve_calories(
        base: BaseTargets, profile: UserAdjustmentProfile, tdee_kcal: float
    ) -> float:
        """Override manuel prioritaire, sinon modulation par l'aggressivité."""
        if profile.manual_calories_override is not None:
            return float(profile.manual_calories_override)
        deficit_base = tdee_kcal - base.calories
        return tdee_kcal - (deficit_base * profile.aggressiveness_factor)

    @staticmethod
    def _resolve_proteines(base: BaseTargets, profile: UserAdjustmentProfile) -> float:
        """Override manuel protéines prioritaire, sinon valeur de base."""
        if profile.manual_proteines_override is not None:
            return float(profile.manual_proteines_override)
        return base.proteines

    @staticmethod
    def _enforce_calorie_floor(
        calories: float, bmr_kcal: float, warnings: list[str]
    ) -> float:
        """Plancher absolu BMR+100 — s'applique même sur un override manuel."""
        floor = bmr_kcal + _ABSOLUTE_MIN_CALORIES_OVER_BMR
        if calories < floor:
            msg = _WARN_CALORIES_FLOOR.format(attempted=calories, floor=floor)
            logger.warning(msg)
            warnings.append(msg)
            return floor
        return calories

    @staticmethod
    def _enforce_proteines_cap(
        proteines: float, weight_kg: float, warnings: list[str]
    ) -> float:
        """Plafond protéines = poids × 3.5 g/kg."""
        cap = weight_kg * _MAX_PROTEINES_G_PER_KG
        if proteines > cap:
            msg = _WARN_PROTEINES_CAP.format(attempted=proteines, cap=cap)
            logger.warning(msg)
            warnings.append(msg)
            return cap
        return proteines
