"""
A3 sheet framework (decision D-13): border, title block, plan view transform
with automatic scale, grid lines with bubbles (letters along X, numbers along
Y), dimension chains, schedule tables and notes.  All values in paper mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .primitives import Drawing

SHEET_W, SHEET_H = 420.0, 297.0                 # A3 landscape
BORDER = (20.0, 10.0, 410.0, 287.0)             # x0, y0, x1, y1 (20 mm binding margin)
TITLE_BLOCK = (280.0, 10.0, 410.0, 60.0)        # bottom-right
SIDE_PANEL = (280.0, 60.0, 410.0, 287.0)        # schedules
PLAN_AREA = (25.0, 38.0, 275.0, 282.0)          # plan views (notes below)
NOTES_AREA = (25.0, 12.0, 275.0, 36.0)
PLAN_SCALES = [50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000]

PRELIM = "PRELIMINARY - NOT FOR CONSTRUCTION"


def grid_letter(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA (I and O skipped, as is common practice)."""
    letters = [c for c in "ABCDEFGHJKLMNPQRSTUVWXYZ"]
    s = ""
    n = i
    while True:
        s = letters[n % len(letters)] + s
        n = n // len(letters) - 1
        if n < 0:
            return s


@dataclass
class Sheet:
    number: str
    title: str
    scale: str
    drawing: Drawing
    kind: str = ""


@dataclass
class View:
    """Model metres -> paper mm: px = ox + (x - x0) * 1000 / scale."""
    scale: float
    ox: float
    oy: float
    x0: float = 0.0
    y0: float = 0.0

    def p(self, x: float, y: float) -> Tuple[float, float]:
        return (self.ox + (x - self.x0) * 1000.0 / self.scale, self.oy + (y - self.y0) * 1000.0 / self.scale)

    def L(self, mm_model: float) -> float:
        """Model millimetres -> paper millimetres."""
        return mm_model / self.scale


def plan_view(xs: Sequence[float], ys: Sequence[float], area=PLAN_AREA, margin=29.0) -> View:
    """Smallest standard scale fitting the plan extents (+ margin for bubbles and dimensions)."""
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w_m, h_m = max(x1 - x0, 0.1), max(y1 - y0, 0.1)
    aw, ah = area[2] - area[0] - 2 * margin, area[3] - area[1] - 2 * margin
    scale = next((s for s in PLAN_SCALES if w_m * 1000 / s <= aw and h_m * 1000 / s <= ah), PLAN_SCALES[-1])
    pw, ph = w_m * 1000 / scale, h_m * 1000 / scale
    ox = area[0] + (area[2] - area[0] - pw) / 2.0
    oy = area[1] + (area[3] - area[1] - ph) / 2.0
    return View(scale, ox, oy, x0, y0)


def new_sheet(number: str, title: str, scale_text: str, project: Dict[str, str],
              side_panel: bool = True) -> Sheet:
    d = Drawing(SHEET_W, SHEET_H)
    x0, y0, x1, y1 = BORDER
    d.rect(5, 5, SHEET_W - 10, SHEET_H - 10, lw="thin", layer="BORDER")
    d.rect(x0, y0, x1 - x0, y1 - y0, lw="heavy", layer="BORDER")
    if side_panel:
        d.line(SIDE_PANEL[0], SIDE_PANEL[1], SIDE_PANEL[0], SIDE_PANEL[3], lw="medium", layer="BORDER")
    _title_block(d, number, title, scale_text, project)
    return Sheet(number, title, scale_text, d)


def _title_block(d: Drawing, number, title, scale_text, project):
    x0, y0, x1, y1 = TITLE_BLOCK
    d.rect(x0, y0, x1 - x0, y1 - y0, lw="medium", layer="TITLE")
    rows = [y0 + 10, y0 + 18, y0 + 26, y0 + 34, y0 + 42]
    for yy in rows:
        d.line(x0, yy, x1, yy, lw="thin", layer="TITLE")
    d.line(x0 + 65, y0, x0 + 65, y0 + 26, lw="thin", layer="TITLE")
    d.text(x0 + 2, y1 - 4, "StructOptima", size=3.5, bold=True, valign="middle", layer="TITLE")
    d.text(x1 - 2, y1 - 4, PRELIM, size=2.4, bold=True, halign="right", valign="middle", color="red", layer="TITLE")
    d.text(x0 + 2, rows[3] + 4, f"PROJECT: {project.get('project', '')}"[:70], size=2.3, valign="middle", layer="TITLE")
    d.text(x0 + 2, rows[2] + 4, f"DRAWING: {title}"[:70], size=2.5, bold=True, valign="middle", layer="TITLE")
    d.text(x0 + 2, rows[1] + 4, f"ENGINEER: {project.get('engineer', '') or '-'}"[:40], size=2.0, valign="middle", layer="TITLE")
    d.text(x0 + 67, rows[1] + 4, f"DATE: {project.get('date', '')}", size=2.0, valign="middle", layer="TITLE")
    d.text(x0 + 2, rows[0] + 4, f"REF: {project.get('ref', '') or '-'}"[:40], size=2.0, valign="middle", layer="TITLE")
    d.text(x0 + 67, rows[0] + 4, f"SCALE: {scale_text}   REV: P0", size=2.0, valign="middle", layer="TITLE")
    d.text(x0 + 2, y0 + 5, "SHEET", size=2.0, valign="middle", layer="TITLE")
    d.text(x0 + 30, y0 + 5, number, size=4.0, bold=True, valign="middle", layer="TITLE")
    d.text(x0 + 67, y0 + 5, project.get("status_line", ""), size=2.0, valign="middle",
           color="red" if "FAIL" in project.get("status_line", "") else "black", layer="TITLE")


def notes(d: Drawing, lines: List[str], area=NOTES_AREA):
    x0, y0, x1, y1 = area
    d.text(x0, y1 - 1, "NOTES", size=2.5, bold=True, valign="top", layer="NOTES")
    y = y1 - 5.0
    step = min(3.0, (y1 - y0 - 5.0) / max(len(lines), 1))
    for i, s in enumerate(lines, 1):
        if y - 1.9 < y0 - 1.0:
            break
        d.text(x0, y, f"{i}. {s}", size=1.8, valign="top", layer="NOTES")
        y -= step


def table(d: Drawing, x: float, y_top: float, cols: List[Tuple[str, float]], rows: List[List[str]],
          row_h: float = 4.6, size: float = 1.9, title: Optional[str] = None,
          row_colors: Optional[List[str]] = None, max_bottom: float = 62.0) -> int:
    """Draw a schedule table; returns the number of rows that fitted."""
    if title:
        d.text(x, y_top + 1.5, title, size=2.6, bold=True, layer="SCHEDULE")
    width = sum(w for _, w in cols)
    y = y_top
    d.rect(x, y - row_h, width, row_h, lw="thin", fill="lightgrey", layer="SCHEDULE")
    cx = x
    for h, w in cols:
        d.text(cx + 1, y - row_h / 2, h, size=size, bold=True, valign="middle", layer="SCHEDULE")
        cx += w
    y -= row_h
    fitted = 0
    for k, r in enumerate(rows):
        if y - row_h < max_bottom:
            break
        color = (row_colors[k] if row_colors else None) or "black"
        d.rect(x, y - row_h, width, row_h, lw="thin", layer="SCHEDULE")
        cx = x
        for (h, w), v in zip(cols, r):
            d.text(cx + 1, y - row_h / 2, str(v), size=size, valign="middle", color=color, layer="SCHEDULE")
            cx += w
        y -= row_h
        fitted += 1
    cx = x
    for _, w in cols[:-1]:
        cx += w
        d.line(cx, y_top, cx, y, lw="thin", layer="SCHEDULE")
    return fitted


def grid(d: Drawing, v: View, xs: Sequence[float], ys: Sequence[float], ext: float = 9.0, r: float = 3.6):
    """Grid lines (dash-dot) with bubbles: letters along X at top and bottom,
    numbers along Y at left and right."""
    (px0, py0), (px1, py1) = v.p(min(xs), min(ys)), v.p(max(xs), max(ys))
    for i, x in enumerate(sorted(xs)):
        px, _ = v.p(x, 0)
        d.line(px, py0 - ext, px, py1 + ext, lw="thin", ltype="dashdot", color="grey", layer="GRID")
        for yy, sign in ((py1 + ext + r, 1), (py0 - ext - r, -1)):
            d.circle(px, yy, r, lw="thin", layer="GRID")
            d.text(px, yy, grid_letter(i), size=2.8, halign="center", valign="middle", layer="GRID")
    for j, y in enumerate(sorted(ys)):
        _, py = v.p(0, y)
        d.line(px0 - ext, py, px1 + ext, py, lw="thin", ltype="dashdot", color="grey", layer="GRID")
        for xx in (px0 - ext - r, px1 + ext + r):
            d.circle(xx, py, r, lw="thin", layer="GRID")
            d.text(xx, py, str(j + 1), size=2.8, halign="center", valign="middle", layer="GRID")


def dim_chain(d: Drawing, pts: Sequence[float], fixed: float, horizontal: bool, labels_mm: Sequence[float],
              size: float = 1.8):
    """Dimension line through successive paper coordinates with 45-degree ticks."""
    t = 1.0
    if horizontal:
        d.line(pts[0], fixed, pts[-1], fixed, lw="thin", layer="DIMENSIONS")
        for p in pts:
            d.line(p - t, fixed - t, p + t, fixed + t, lw="medium", layer="DIMENSIONS")
            d.line(p, fixed - 2, p, fixed + 2, lw="thin", layer="DIMENSIONS")
        for a, b, lab in zip(pts, pts[1:], labels_mm):
            d.text((a + b) / 2, fixed + 0.8, f"{lab:.0f}", size=size, halign="center", layer="DIMENSIONS")
    else:
        d.line(fixed, pts[0], fixed, pts[-1], lw="thin", layer="DIMENSIONS")
        for p in pts:
            d.line(fixed - t, p - t, fixed + t, p + t, lw="medium", layer="DIMENSIONS")
            d.line(fixed - 2, p, fixed + 2, p, lw="thin", layer="DIMENSIONS")
        for a, b, lab in zip(pts, pts[1:], labels_mm):
            d.text(fixed - 0.8, (a + b) / 2, f"{lab:.0f}", size=size, halign="center", valign="bottom",
                   rot=90, layer="DIMENSIONS")


def plan_dimensions(d: Drawing, v: View, xs: Sequence[float], ys: Sequence[float]):
    """Bay and overall dimension chains below and left of the plan."""
    xs, ys = sorted(xs), sorted(ys)
    _, py0 = v.p(0, ys[0])
    px0, _ = v.p(xs[0], 0)
    pxs = [v.p(x, 0)[0] for x in xs]
    pys = [v.p(0, y)[1] for y in ys]
    dim_chain(d, pxs, py0 - 21, True, [(b - a) * 1000 for a, b in zip(xs, xs[1:])])
    dim_chain(d, [pxs[0], pxs[-1]], py0 - 26, True, [(xs[-1] - xs[0]) * 1000])
    dim_chain(d, pys, px0 - 21, False, [(b - a) * 1000 for a, b in zip(ys, ys[1:])])
    dim_chain(d, [pys[0], pys[-1]], px0 - 26, False, [(ys[-1] - ys[0]) * 1000])


def north_arrow(d: Drawing, x: float, y: float):
    d.polyline([(x, y + 7), (x - 2.2, y), (x, y + 1.8), (x + 2.2, y)], closed=True, lw="thin", fill="black", layer="NOTES")
    d.text(x, y + 8.5, "N", size=2.6, bold=True, halign="center", layer="NOTES")


def scale_bar(d: Drawing, x: float, y: float, scale: float):
    """Scale bar showing 0-5 m."""
    seg = 1000.0 / scale
    for i in range(5):
        d.rect(x + i * seg, y, seg, 1.5, lw="thin", fill="black" if i % 2 == 0 else None, layer="NOTES")
    d.text(x, y + 2.5, "0", size=1.8, halign="center", layer="NOTES")
    d.text(x + 5 * seg, y + 2.5, "5 m", size=1.8, halign="center", layer="NOTES")
