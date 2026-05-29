import csv
import io
from collections import defaultdict
from fastapi.responses import StreamingResponse
from app.schemas.shopping_list import ShoppingList

_DEJAVU_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

_CATEGORY_LABELS: dict[str, str] = {
    "enums.type_of_ingredient.vegetable": "Légumes",
    "enums.type_of_ingredient.fruit":     "Fruits",
    "enums.type_of_ingredient.meat":      "Viandes",
    "enums.type_of_ingredient.fish":      "Poissons",
    "enums.type_of_ingredient.dairy":     "Produits laitiers",
    "enums.type_of_ingredient.grain":     "Céréales & féculents",
    "enums.type_of_ingredient.legume":    "Légumineuses",
    "enums.type_of_ingredient.egg":       "Oeufs",
    "enums.type_of_ingredient.fat":       "Matières grasses",
    "enums.type_of_ingredient.condiment": "Condiments",
    "enums.type_of_ingredient.herb":      "Herbes & épices",
    "enums.type_of_ingredient.drink":     "Boissons",
    "enums.type_of_ingredient.other":     "Divers",
}


def _category_label(cat: str | None) -> str:
    if not cat:
        return "Divers"
    return _CATEGORY_LABELS.get(cat, cat.split(".")[-1].replace("_", " ").capitalize())


def export_shopping_list(sl: ShoppingList, format: str) -> StreamingResponse:
    if format == "csv":
        return _to_csv(sl)
    return _to_pdf(sl)


def _to_csv(sl: ShoppingList) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Ingrédient", "Quantité", "Unité", "Catégorie"])
    for item in sl.items:
        writer.writerow(
            [item.ingredient_name, item.total_quantity, item.unit, item.category or ""]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=shopping-list-{sl.menu_id}.csv"
        },
    )


def _to_pdf(sl: ShoppingList) -> StreamingResponse:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.add_font("DejaVu", fname=_DEJAVU_PATH)
    pdf.add_font("DejaVu", style="B", fname=_DEJAVU_BOLD_PATH)

    # Title
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 12, f"Liste de courses - semaine du {sl.start_date}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("DejaVu", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"{sl.nb_persons} personne(s)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    groups: dict[str, list] = defaultdict(list)
    for item in sl.items:
        groups[item.category or ""].append(item)

    col_ingredient = 95
    col_qty        = 35
    col_unit       = 30
    header_color   = (230, 240, 250)
    row_alt_color  = (248, 248, 248)

    for cat_key, items in groups.items():
        pdf.set_fill_color(60, 100, 160)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("DejaVu", "B", 11)
        pdf.cell(0, 8, f"  {_category_label(cat_key)}", new_x="LMARGIN", new_y="NEXT", fill=True)

        pdf.set_fill_color(*header_color)
        pdf.set_text_color(60, 60, 60)
        pdf.set_font("DejaVu", "B", 9)
        pdf.cell(col_ingredient, 7, "Ingrédient", border=1, fill=True)
        pdf.cell(col_qty, 7, "Quantité", border=1, fill=True, align="R")
        pdf.cell(col_unit, 7, "Unité", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("DejaVu", "", 10)
        for i, item in enumerate(items):
            pdf.set_fill_color(*(row_alt_color if i % 2 == 0 else (255, 255, 255)))
            pdf.set_text_color(40, 40, 40)
            name = item.ingredient_name[:50]
            pdf.cell(col_ingredient, 7, name, border="LR", fill=True)
            pdf.cell(col_qty, 7, str(item.total_quantity), border="LR", fill=True, align="R")
            pdf.cell(col_unit, 7, item.unit[:12], border="LR", fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_fill_color(200, 200, 200)
        pdf.cell(col_ingredient + col_qty + col_unit, 0.3, "", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(5)

    return StreamingResponse(
        iter([bytes(pdf.output())]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=shopping-list-{sl.menu_id}.pdf"
        },
    )
