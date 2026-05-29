import base64
import csv
import io
<<<<<<< Updated upstream
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
=======
from functools import lru_cache
from pathlib import Path

from fastapi.responses import StreamingResponse
from app.schemas.shopping_list import ShoppingList

_EMBLEM_PATH = Path(__file__).resolve().parent.parent / "assets" / "emblem-flame-ink.png"


@lru_cache(maxsize=1)
def _emblem_data_uri() -> str:
    """Return the watermark emblem as a base64 data URI (cached, read once)."""
    try:
        encoded = base64.b64encode(_EMBLEM_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return ""
>>>>>>> Stashed changes


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

<<<<<<< Updated upstream
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
=======
    rows = "".join(
        f"<tr><td>{i.ingredient_name}</td><td>{i.total_quantity}</td>"
        f"<td>{i.unit}</td><td>{i.category or ''}</td></tr>"
        for i in sl.items
    )
    emblem = _emblem_data_uri()
    watermark = (
        f'<div class="watermark"><img src="{emblem}" alt="" /></div>' if emblem else ""
    )
    html = f"""<html><head><style>
    @page {{ margin: 2cm; }}
    body {{ font-family: sans-serif; }}
    .watermark {{
      position: fixed;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      width: 60%;
      opacity: 0.07;
      z-index: -1;
    }}
    .watermark img {{ width: 100%; }}
    </style></head><body>
    {watermark}
    <h1>Liste de courses — semaine du {sl.start_date}</h1>
    <p>{sl.nb_persons} personne(s)</p>
    <table border="1" cellpadding="4" style="border-collapse:collapse;width:100%">
      <thead><tr><th>Ingrédient</th><th>Quantité</th><th>Unité</th><th>Catégorie</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></body></html>"""
>>>>>>> Stashed changes

    return StreamingResponse(
        iter([bytes(pdf.output())]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=shopping-list-{sl.menu_id}.pdf"
        },
    )
