import pytest

from app.services.macro_calculator import MacroCalculator


def _make_ingredient(
    slug="farine-sarrasin",
    grammes=200.0,
    cal=340.0,
    prot=13.0,
    gluc=71.0,
    lipid=3.0,
    raw="200g de farine",
):
    return MacroCalculator.compute_ingredient_macros(
        nutrition_item_slug=slug,
        grammes=grammes,
        cal_100=cal,
        prot_100=prot,
        gluc_100=gluc,
        lipid_100=lipid,
        raw_text=raw,
    )


class TestMacroCalculator:
    @pytest.fixture
    def calculator(self) -> MacroCalculator:
        return MacroCalculator()

    @pytest.mark.unit
    def test_compute_100g_equals_per_100g_values(self):
        """100g → macros == valeurs pour 100g."""
        im = MacroCalculator.compute_ingredient_macros(
            "sarrasin", 100.0, 340.0, 13.0, 71.0, 3.0
        )
        assert im.calories == pytest.approx(340.0)
        assert im.proteines == pytest.approx(13.0)
        assert im.glucides == pytest.approx(71.0)
        assert im.lipides == pytest.approx(3.0)

    @pytest.mark.unit
    def test_compute_200g_doubles_values(self):
        """200g → macros × 2."""
        im = MacroCalculator.compute_ingredient_macros(
            "sarrasin", 200.0, 340.0, 13.0, 71.0, 3.0
        )
        assert im.calories == pytest.approx(680.0)
        assert im.proteines == pytest.approx(26.0)

    @pytest.mark.unit
    def test_compute_50g_halves_values(self):
        """50g → macros / 2."""
        im = MacroCalculator.compute_ingredient_macros(
            "sarrasin", 50.0, 340.0, 13.0, 71.0, 3.0
        )
        assert im.calories == pytest.approx(170.0)

    @pytest.mark.unit
    def test_compute_preserves_slug_and_raw_text(self):
        """matched_slug et raw_text sont conservés."""
        im = MacroCalculator.compute_ingredient_macros(
            "huile-olive", 20.0, 900.0, 0.0, 0.0, 100.0, raw_text="2 cs d'huile"
        )
        assert im.matched_slug == "huile-olive"
        assert im.raw_text == "2 cs d'huile"
        assert im.grammes == pytest.approx(20.0)

    @pytest.mark.unit
    def test_calculate_empty_list_returns_zeros(self, calculator):
        """Aucun ingrédient → total et per_serving à zéro."""
        total, per_serving = calculator.calculate([])
        assert total.calories == 0.0
        assert total.proteines == 0.0
        assert per_serving.glucides == 0.0

    @pytest.mark.unit
    def test_calculate_single_ingredient_one_serving(self, calculator):
        """1 ingrédient, 1 portion → total == per_serving."""
        im = _make_ingredient(grammes=200.0, cal=340.0, prot=13.0, gluc=71.0, lipid=3.0)
        total, per_serving = calculator.calculate([im], servings=1)
        assert total.calories == pytest.approx(680.0)
        assert per_serving.calories == pytest.approx(680.0)

    @pytest.mark.unit
    def test_calculate_per_serving_divides_correctly(self, calculator):
        """4 portions → per_serving = total / 4."""
        im = _make_ingredient(grammes=200.0, cal=340.0, prot=12.0, gluc=60.0, lipid=4.0)
        total, per_serving = calculator.calculate([im], servings=4)
        assert per_serving.calories == pytest.approx(total.calories / 4, rel=1e-3)
        assert per_serving.proteines == pytest.approx(total.proteines / 4, rel=1e-3)

    @pytest.mark.unit
    def test_calculate_servings_zero_treated_as_one(self, calculator):
        """servings=0 → per_serving == total (pas de ZeroDivisionError)."""
        im = _make_ingredient(grammes=100.0, cal=200.0, prot=5.0, gluc=30.0, lipid=8.0)
        total, per_serving = calculator.calculate([im], servings=0)
        assert per_serving.calories == pytest.approx(total.calories)

    @pytest.mark.unit
    def test_calculate_multiple_ingredients_sum(self, calculator):
        """2 ingrédients → somme correcte."""
        im1 = _make_ingredient(slug="a", grammes=100.0, cal=200.0, prot=5.0, gluc=30.0, lipid=8.0)
        im2 = _make_ingredient(slug="b", grammes=50.0, cal=400.0, prot=20.0, gluc=10.0, lipid=15.0)
        total, _ = calculator.calculate([im1, im2])
        assert total.calories == pytest.approx(200.0 + 200.0)
        assert total.proteines == pytest.approx(5.0 + 10.0)

    @pytest.mark.unit
    def test_calculate_negative_servings_treated_as_one(self, calculator):
        """servings négatif → per_serving == total."""
        im = _make_ingredient(grammes=100.0, cal=100.0, prot=5.0, gluc=10.0, lipid=3.0)
        total, per_serving = calculator.calculate([im], servings=-1)
        assert per_serving.calories == pytest.approx(total.calories)