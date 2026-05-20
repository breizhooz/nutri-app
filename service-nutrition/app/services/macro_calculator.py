from dataclasses import dataclass


@dataclass
class IngredientMacros:
    raw_text: str
    matched_slug: str
    grammes: float
    calories: float
    proteines: float
    glucides: float
    lipides: float


@dataclass
class RecipeMacros:
    calories: float
    proteines: float
    glucides: float
    lipides: float


class MacroCalculator:
    """Calcul pur des macros, sans I/O."""

    def calculate(
        self,
        ingredients: list[IngredientMacros],
        servings: int = 1,
    ) -> tuple[RecipeMacros, RecipeMacros]:
        """Retourne (total, per_serving)."""
        total = RecipeMacros(
            calories=round(sum(i.calories for i in ingredients), 2),
            proteines=round(sum(i.proteines for i in ingredients), 2),
            glucides=round(sum(i.glucides for i in ingredients), 2),
            lipides=round(sum(i.lipides for i in ingredients), 2),
        )
        s = max(servings, 1)
        per_serving = RecipeMacros(
            calories=round(total.calories / s, 2),
            proteines=round(total.proteines / s, 2),
            glucides=round(total.glucides / s, 2),
            lipides=round(total.lipides / s, 2),
        )
        return total, per_serving

    @staticmethod
    def compute_ingredient_macros(
        nutrition_item_slug: str,
        grammes: float,
        cal_100: float,
        prot_100: float,
        gluc_100: float,
        lipid_100: float,
        raw_text: str = "",
    ) -> IngredientMacros:
        factor = grammes / 100
        return IngredientMacros(
            raw_text=raw_text,
            matched_slug=nutrition_item_slug,
            grammes=grammes,
            calories=round(cal_100 * factor, 2),
            proteines=round(prot_100 * factor, 2),
            glucides=round(gluc_100 * factor, 2),
            lipides=round(lipid_100 * factor, 2),
        )