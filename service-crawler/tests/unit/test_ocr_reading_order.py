from app.services.ocr_reading_order import ReadingOrder, TextBox


def _box(text, x_min, y_min, x_max, height=30):
    return TextBox(text, x_min, x_max, y_min, y_min + height)


def test_empty():
    assert ReadingOrder().order([]) == []


def test_single_column_top_to_bottom():
    boxes = [
        _box("Étape 2", 50, 200, 600),
        _box("Titre", 50, 20, 400),
        _box("Étape 1", 50, 100, 650),
    ]
    assert ReadingOrder().order(boxes) == ["Titre", "Étape 1", "Étape 2"]


def test_same_row_boxes_are_joined_left_to_right():
    boxes = [_box("de farine", 200, 100, 400, 30), _box("250 g", 50, 104, 150, 30)]
    assert ReadingOrder().order(boxes) == ["250 g de farine"]


def test_two_columns_read_one_after_the_other():
    """Lignes alignées gauche/droite (magazine) : pas d'entrelacement."""
    left = [_box(f"G{i}", 50, 100 + 60 * i, 800) for i in range(3)]
    right = [_box(f"D{i}", 950, 100 + 60 * i, 1700) for i in range(3)]
    assert ReadingOrder().order(left + right) == ["G0", "G1", "G2", "D0", "D1", "D2"]


def test_spanning_title_is_read_before_the_columns():
    title = _box("Blanquette de veau", 50, 20, 1700, 40)
    left = [_box(f"G{i}", 50, 100 + 60 * i, 800) for i in range(2)]
    right = [_box(f"D{i}", 950, 100 + 60 * i, 1700) for i in range(2)]
    assert ReadingOrder().order([*right, title, *left]) == [
        "Blanquette de veau",
        "G0",
        "G1",
        "D0",
        "D1",
    ]


def test_spanning_block_splits_page_into_bands():
    """Colonnes au-dessus puis en dessous d'un bandeau pleine largeur."""
    boxes = [
        _box("G-haut", 50, 100, 800),
        _box("D-haut", 950, 100, 1700),
        _box("BANDEAU", 50, 300, 1700),
        _box("G-bas", 50, 500, 800),
        _box("D-bas", 950, 500, 1700),
    ]
    assert ReadingOrder().order(boxes) == [
        "G-haut",
        "D-haut",
        "BANDEAU",
        "G-bas",
        "D-bas",
    ]


def test_short_ingredient_column_next_to_steps_is_a_column():
    """Ingrédients courts (~20 % de large) face aux étapes : vraie colonne."""
    left = [_box(f"ingrédient {i}", 50, 100 + 60 * i, 340) for i in range(3)]
    right = [_box(f"étape {i}", 1000, 100 + 60 * i, 1350) for i in range(3)]
    assert ReadingOrder().order(right + left) == [
        "ingrédient 0",
        "ingrédient 1",
        "ingrédient 2",
        "étape 0",
        "étape 1",
        "étape 2",
    ]


def test_ingredient_table_keeps_name_next_to_quantity():
    """Quantités étroites alignées à droite : ce n'est PAS une colonne de texte."""
    boxes = [
        _box("Farine", 50, 100, 400),
        _box("250 g", 1500, 102, 1650),
        _box("Sucre en poudre", 50, 160, 500),
        _box("100 g", 1500, 162, 1650),
    ]
    assert ReadingOrder().order(boxes) == ["Farine 250 g", "Sucre en poudre 100 g"]


def test_textbox_from_points():
    box = TextBox.from_points("x", [[10, 20], [110, 22], [109, 52], [9, 50]])
    assert (box.x_min, box.x_max, box.y_min, box.y_max) == (9, 110, 20, 52)
    assert box.width == 101
    assert box.y_center == 36
