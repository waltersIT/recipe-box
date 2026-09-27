"""Rebuild reading order from positioned text (OCR results or PDF text runs).

Screenshots and PDFs of recipes are often laid out in two columns (ingredients
on the left, steps on the right). Reading their text top-to-bottom would
interleave the columns, so we:

  1. split the page into horizontal bands wherever there's vertical whitespace,
  2. merge consecutive bands that share a common vertical gutter (a column gap),
  3. read each column group left column first, then right,
  4. join boxes that sit on the same row into lines.

Coordinates use a top-left origin in any consistent unit (pixels or points).
"""

import re
import statistics
from dataclasses import dataclass


@dataclass
class TextBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1e-6)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    """A line of text in reading order.

    `height` is the text height relative to the page's typical line (1.0 =
    body text), used to spot titles. `gap_before` marks extra vertical space
    above the line (a paragraph break). `fills_width` means the line runs to
    the right edge of its column, i.e. it probably wraps onto the next line.
    """

    text: str
    height: float = 1.0
    gap_before: bool = False
    fills_width: bool = False


_QUANTITY_ONLY = re.compile(
    r"^[\d½¼¾⅓⅔⅛⅜⅝⅞/.,\s\-–]+\s*(cups?|c\.|tbsps?|tablespoons?|tsps?|teaspoons?|oz|ounces?|lbs?|pounds?|g|grams?|kg|ml|l|liters?|litres?|pinch(es)?|cloves?|large|medium|small|cans?)?\.?$",
    re.I,
)


def _bands(boxes: list[TextBox]) -> list[list[TextBox]]:
    """Group boxes into horizontal bands separated by vertical whitespace."""
    bands: list[list[TextBox]] = []
    bottom = None
    for box in sorted(boxes, key=lambda b: b.y0):
        if bands and box.y0 < bottom:
            bands[-1].append(box)
            bottom = max(bottom, box.y1)
        else:
            bands.append([box])
            bottom = box.y1
    return bands


def _side_by_side(boxes: list[TextBox], gap: tuple[float, float]) -> bool:
    """True if some text left of the gap sits at the same height as text right of it."""
    left = [b for b in boxes if b.x1 <= gap[0]]
    right = [b for b in boxes if b.x0 >= gap[1]]
    return any(
        min(l.y1, r.y1) - max(l.y0, r.y0) > 0.3 * min(l.height, r.height) for l in left for r in right
    )


def _gutter(boxes: list[TextBox], min_width: float) -> tuple[float, float] | None:
    """Widest empty vertical strip that has text beside it on both sides.

    A centred title above left-aligned text also leaves an empty strip, but
    nothing sits side by side across it, so it isn't treated as a column gap.
    """
    if len(boxes) < 2:
        return None
    spans = sorted((b.x0, b.x1) for b in boxes)
    gaps = []
    reach = spans[0][1]
    for x0, x1 in spans[1:]:
        if x0 - reach >= min_width:
            gaps.append((reach, x0))
        reach = max(reach, x1)
    for gap in sorted(gaps, key=lambda g: g[1] - g[0], reverse=True):
        if _side_by_side(boxes, gap):
            return gap
    return None


def _is_table(boxes: list[TextBox], gutter: tuple[float, float]) -> bool:
    """A 'gutter' with only quantities on its left is a table (amount | ingredient), not columns."""
    left = [b for b in boxes if b.x1 <= gutter[0]]
    if not left:
        return False
    quantity_like = sum(1 for b in left if _QUANTITY_ONLY.match(b.text.strip()))
    return quantity_like / len(left) >= 0.6


def _balanced(boxes: list[TextBox], gutter: tuple[float, float]) -> bool:
    """Columns run alongside each other; a short row of items above a list doesn't.

    Without this, a "PREP TIME  COOK TIME  TOTAL TIME" row (or a phone's
    status bar) would make every short line below it look like a left column.
    """
    left = [b for b in boxes if b.x1 <= gutter[0]]
    right = [b for b in boxes if b.x0 >= gutter[1]]
    return len(_bands(left)) >= 3 and len(_bands(right)) >= 3


def _column_groups(boxes: list[TextBox], min_gutter: float) -> list[tuple[list[TextBox], tuple | None]]:
    groups: list[tuple[list[TextBox], tuple | None]] = []
    current: list[TextBox] = []
    for band in _bands(boxes):
        if not current:
            current = list(band)
            continue
        merged = current + band
        merged_gutter = _gutter(merged, min_gutter)
        if merged_gutter and not _is_table(merged, merged_gutter):
            two_sided = any(b.x1 <= merged_gutter[0] for b in band) and any(b.x0 >= merged_gutter[1] for b in band)
            if two_sided or _balanced(merged, merged_gutter):
                current = merged
                continue
        current_gutter = _gutter(current, min_gutter)
        band_gutter = _gutter(band, min_gutter)
        current_has = bool(current_gutter and not _is_table(current, current_gutter))
        band_has = bool(band_gutter and not _is_table(band, band_gutter))
        if not current_has and not band_has:
            current = merged
        else:
            groups.append((current, current_gutter if current_has else None))
            current = list(band)
    if current:
        gutter = _gutter(current, min_gutter)
        groups.append((current, gutter if gutter and not _is_table(current, gutter) else None))
    return groups


def _order(boxes: list[TextBox], min_gutter: float, depth: int = 0) -> list[list[TextBox]]:
    """Return boxes split into column blocks, in reading order."""
    if not boxes:
        return []
    blocks: list[list[TextBox]] = []
    for group, gutter in _column_groups(boxes, min_gutter):
        if gutter and depth < 4:
            split = (gutter[0] + gutter[1]) / 2
            left = [b for b in group if (b.x0 + b.x1) / 2 < split]
            right = [b for b in group if (b.x0 + b.x1) / 2 >= split]
            blocks.extend(_order(left, min_gutter, depth + 1))
            blocks.extend(_order(right, min_gutter, depth + 1))
        else:
            blocks.append(group)
    return blocks


def _rows(block: list[TextBox]) -> list[list[TextBox]]:
    """Group boxes into rows (boxes whose vertical extents mostly overlap)."""
    rows: list[list[TextBox]] = []
    for box in sorted(block, key=lambda b: (b.cy, b.x0)):
        if rows:
            row = rows[-1]
            top = min(b.y0 for b in row)
            bottom = max(b.y1 for b in row)
            overlap = min(bottom, box.y1) - max(top, box.y0)
            if overlap > 0.5 * min(box.height, bottom - top):
                row.append(box)
                continue
        rows.append([box])
    return [sorted(row, key=lambda b: b.x0) for row in rows]


def boxes_to_lines(boxes: list[TextBox]) -> list[Line]:
    """Order one page's boxes into lines of text."""
    boxes = [b for b in boxes if b.text and b.text.strip()]
    if not boxes:
        return []
    median_height = statistics.median(b.height for b in boxes)
    lines: list[Line] = []
    for block in _order(boxes, min_gutter=1.5 * median_height):
        rows = _rows(block)
        right_edge = max(b.x1 for b in block)
        left_edge = min(b.x0 for b in block)
        width = max(right_edge - left_edge, 1e-6)
        previous_bottom = None
        for index, row in enumerate(rows):
            text = " ".join(b.text.strip() for b in row)
            top = min(b.y0 for b in row)
            row_height = statistics.median(b.height for b in row)
            gap = (top - previous_bottom) if previous_bottom is not None else 0.0
            lines.append(
                Line(
                    text=text,
                    height=row_height / median_height,
                    # The first line of each column block also starts a new paragraph.
                    gap_before=index == 0 or gap > 0.9 * median_height,
                    fills_width=(max(b.x1 for b in row) - left_edge) / width > 0.85,
                )
            )
            previous_bottom = max(b.y1 for b in row)
    return lines


def text_to_lines(text: str) -> list[Line]:
    """Plain text (no geometry) to lines; blank lines become paragraph breaks."""
    lines: list[Line] = []
    gap = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            gap = True
            continue
        lines.append(Line(text=stripped, gap_before=gap))
        gap = False
    return lines
