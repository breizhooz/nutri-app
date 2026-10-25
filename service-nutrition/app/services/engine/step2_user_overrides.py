"""Étape 2 — Ajustements UI sur les cibles reçues de l'appareil.

Le serveur n'a plus de donnée corporelle (allègement RGPD, 2026-10-24) : les
cibles arrivent calculées par l'appareil, qui applique les garde-fous
physiologiques (plancher BMR, cf. e2e-core ``computeTargetCalories``). Ici, on
n'applique que les overrides manuels et les tolérances de l'UI.
"""

from app.schemas.engine import DailyTargets, FinalTargets, UserAdjustmentProfile


class UserOverridesService:
    """Fusionne cibles reçues et ajustements UI."""

    def apply(
        self, targets: DailyTargets, profile: UserAdjustmentProfile
    ) -> FinalTargets:
        """Overrides manuels prioritaires ; lipides/glucides repris tels quels."""
        calories = (
            float(profile.manual_calories_override)
            if profile.manual_calories_override is not None
            else targets.calories
        )
        proteines = (
            float(profile.manual_proteines_override)
            if profile.manual_proteines_override is not None
            else targets.proteines
        )
        return FinalTargets(
            calories=round(calories, 1),
            proteines=None if proteines is None else round(proteines, 1),
            lipides=None if targets.lipides is None else round(targets.lipides, 1),
            glucides=None if targets.glucides is None else round(targets.glucides, 1),
            tolerances=profile.tolerances,
            filter_priorities=profile.filter_priorities,
        )
