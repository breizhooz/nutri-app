from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextBox:
    """Une ligne détectée par l'OCR et sa boîte englobante (pixels)."""

    text: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @classmethod
    def from_points(cls, text: str, points) -> "TextBox":
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return cls(text, min(xs), max(xs), min(ys), max(ys))


class ReadingOrder:
    """Remet les lignes OCR dans l'ordre de lecture, colonne par colonne.

    RapidOCR renvoie les lignes triées de haut en bas : sur une mise en page en
    colonnes (magazine), les lignes de gauche et de droite s'entrelacent. On
    détecte donc les colonnes (gouttières verticales vides) et on lit chaque
    colonne entière avant la suivante. Un élément « pleine largeur » (titre sur
    toute la page) coupe la page en bandes lues l'une après l'autre.

    Garde-fou tableaux : chaque colonne doit dépasser ``MIN_COLUMN_RATIO`` de la
    largeur du texte. Dans un tableau d'ingrédients « Farine …… 200 g », la
    colonne des quantités est très étroite (~10 %) : il n'est donc PAS découpé
    et reste lu ligne par ligne, le nom à côté de sa quantité. Une colonne
    d'ingrédients courts face aux étapes (~20 %+) reste, elle, une colonne.
    """

    SPANNING_RATIO = 0.6  # plus large que ça → élément pleine largeur (titre…)
    MIN_COLUMN_RATIO = 0.15  # plus étroit → colonne de quantités d'un tableau
    MIN_GAP_RATIO = 0.02  # gouttière minimale entre deux colonnes
    MIN_COLUMN_LINES = 2  # une colonne compte au moins ce nombre de lignes

    def order(self, boxes: list[TextBox]) -> list[str]:
        if not boxes:
            return []
        left = min(b.x_min for b in boxes)
        right = max(b.x_max for b in boxes)
        page_width = max(right - left, 1.0)

        spanning = [b for b in boxes if b.width > self.SPANNING_RATIO * page_width]
        body = [b for b in boxes if b.width <= self.SPANNING_RATIO * page_width]
        columns = self._columns(body, page_width)
        if len(columns) < 2:
            return self._rows(boxes)

        # Bandes horizontales délimitées par les éléments pleine largeur.
        lines: list[str] = []
        cuts = sorted(spanning, key=lambda b: b.y_center)
        bounds = [float("-inf")] + [c.y_center for c in cuts] + [float("inf")]
        for i in range(len(bounds) - 1):
            top, bottom = bounds[i], bounds[i + 1]
            for x_start, x_end in columns:
                in_column = [
                    b
                    for b in body
                    if top < b.y_center <= bottom
                    and x_start <= (b.x_min + b.x_max) / 2 <= x_end
                ]
                lines.extend(self._rows(in_column))
            if i < len(cuts):
                lines.append(cuts[i].text)
        return lines

    def _columns(
        self, body: list[TextBox], page_width: float
    ) -> list[tuple[float, float]]:
        """Intervalles horizontaux occupés par le texte, séparés par des gouttières.

        Renvoie ``[]`` (= une seule colonne) si l'un des intervalles est trop
        étroit (colonne de quantités d'un tableau) ou compte moins de
        ``MIN_COLUMN_LINES`` lignes (mot isolé détaché de sa ligne).
        """
        if len(body) < 2:
            return []
        min_gap = self.MIN_GAP_RATIO * page_width
        spans: list[list[float]] = []  # [x_start, x_end, nb de lignes]
        for b in sorted(body, key=lambda b: b.x_min):
            if spans and b.x_min <= spans[-1][1] + min_gap:
                spans[-1][1] = max(spans[-1][1], b.x_max)
                spans[-1][2] += 1
            else:
                spans.append([b.x_min, b.x_max, 1])
        if len(spans) < 2:
            return []
        for start, end, count in spans:
            too_narrow = (end - start) < self.MIN_COLUMN_RATIO * page_width
            if too_narrow or count < self.MIN_COLUMN_LINES:
                return []
        return [(start, end) for start, end, _ in spans]

    @staticmethod
    def _rows(boxes: list[TextBox]) -> list[str]:
        """Ordre haut→bas ; les boîtes d'une même rangée sont jointes de gauche à droite."""
        rows: list[list[TextBox]] = []
        for b in sorted(boxes, key=lambda b: (b.y_center, b.x_min)):
            if (
                rows
                and abs(b.y_center - rows[-1][0].y_center) <= rows[-1][0].height / 2
            ):
                rows[-1].append(b)
            else:
                rows.append([b])
        return [
            " ".join(b.text for b in sorted(row, key=lambda b: b.x_min)) for row in rows
        ]
