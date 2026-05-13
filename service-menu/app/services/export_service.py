import csv
import io
from fastapi.responses import StreamingResponse
from app.schemas.shopping_list import ShoppingList


def export_shopping_list(sl: ShoppingList, format: str) -> StreamingResponse:
    if format == "csv":
        return _to_csv(sl)
    return _to_pdf(sl)


def _to_csv(sl: ShoppingList) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Ingrédient", "Quantité", "Unité", "Catégorie"])
    for item in sl.items:
        writer.writerow([item.ingredient_name, item.total_quantity, item.unit, item.category or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=shopping-list-{sl.menu_id}.csv"},
    )


def _to_pdf(sl: ShoppingList) -> StreamingResponse:
    from weasyprint import HTML

    rows = "".join(
        f"<tr><td>{i.ingredient_name}</td><td>{i.total_quantity}</td>"
        f"<td>{i.unit}</td><td>{i.category or ''}</td></tr>"
        for i in sl.items
    )
    html = f"""<html><body>
    <h1>Liste de courses — semaine du {sl.start_date}</h1>
    <p>{sl.nb_persons} personne(s)</p>
    <table border="1" cellpadding="4" style="border-collapse:collapse;width:100%">
      <thead><tr><th>Ingrédient</th><th>Quantité</th><th>Unité</th><th>Catégorie</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></body></html>"""

    pdf = HTML(string=html).write_pdf()
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=shopping-list-{sl.menu_id}.pdf"},
    )