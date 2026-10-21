"""
Site drawing set builders.

    S-01  Column layout plan + column schedule
    S-02  Footing layout plan + footing schedule
    S-03  Typical floor beam & slab layout + beam schedule
    S-04  Column and beam cross-sections (1:20)
    S-05  Slab reinforcement plan + slab schedule
    S-06  Footing sections
    S-xxA Schedule continuation sheets when a schedule does not fit

Everything is drawn from the designed model (GridManager schedules, footings,
marks).  Laps, curtailment and anchorage are NOT designed by StructOptima;
sections carry "typical detail" notes.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from .marks import Marks, compute_marks
from ..rebar_detailer import format_interaction_ratio
from .primitives import Drawing
from .sheet import (BORDER, PLAN_AREA, SIDE_PANEL, Sheet, View, grid, new_sheet, north_arrow, notes, plan_dimensions,
                    plan_view, scale_bar, table)

STATUS_COLOR = {"FAIL": "red", "WARN": "orange"}


def _sc(status: str) -> Optional[str]:
    return STATUS_COLOR.get(status)


def _bars(desc: str, default=(0, 0)) -> Tuple[int, int]:
    m = re.match(r"\s*(\d+)-(\d+)#", desc or "")
    return (int(m.group(1)), int(m.group(2))) if m else default


def _spacing(desc: str) -> Optional[float]:
    m = re.search(r"@\s*(\d+)", desc or "")
    return float(m.group(1)) if m else None


def _col_dims(c) -> Tuple[float, float]:
    w, d = c.width_nb, c.depth_nb
    if abs((c.orientation_deg % 180.0) - 90.0) < 1.0:
        w, d = d, w
    return w, d


def _general_notes(gm, extra: Optional[List[str]] = None) -> List[str]:
    out = ["All dimensions in mm, levels in m, unless noted. Do not scale from this drawing.",
           f"Concrete M{gm.fck:.0f}, reinforcement Fe{gm.fy:.0f}. Clear cover: columns {gm.column_cover_mm:.0f}, beams {gm.beam_cover_mm:.0f}, "
           f"slabs {gm.slab_cover_mm:.0f}, footings {gm.footing_cover_mm:.0f} mm.",
           "Members tagged WARN/FAIL (orange/red) need engineering review or redesign - see the design status list.",
           "Laps, curtailment and anchorage are NOT designed by StructOptima: detail per IS 456 / SP 34 (typical).",
           "Preliminary design aid output. Independent verification by a licensed structural engineer is required."]
    return (extra or []) + out


def _draw_voids(d: Drawing, v: View, gm):
    """Cross and label in bays without slab (staircase / voids)."""
    xs, ys = sorted(gm.x_grid_lines), sorted(gm.y_grid_lines)
    for (i, j) in gm.void_bays or []:
        if 0 <= i < len(xs) - 1 and 0 <= j < len(ys) - 1:
            (x0, y0), (x1, y1) = v.p(xs[i], ys[j]), v.p(xs[i + 1], ys[j + 1])
            d.line(x0, y0, x1, y1, lw="thin", color="grey", layer="VOIDS")
            d.line(x0, y1, x1, y0, lw="thin", color="grey", layer="VOIDS")
            d.text((x0 + x1) / 2, (y0 + y1) / 2 + 1, "STAIR / VOID", size=2.0, bold=True, halign="center",
                   valign="bottom", color="grey", layer="VOIDS")
            d.text((x0 + x1) / 2, (y0 + y1) / 2 - 1, "(no slab - stair designed separately)", size=1.5,
                   halign="center", valign="top", color="grey", layer="VOIDS")


def _plan_base(gm, project, number, title, side=True):
    xs, ys = gm.x_grid_lines, gm.y_grid_lines
    v = plan_view(xs, ys)
    sh = new_sheet(number, title, f"1:{v.scale:.0f}", project, side_panel=side)
    d = sh.drawing
    grid(d, v, xs, ys)
    plan_dimensions(d, v, xs, ys)
    north_arrow(d, PLAN_AREA[2] - 6, PLAN_AREA[3] - 14)
    scale_bar(d, PLAN_AREA[0] + 2, PLAN_AREA[1] + 1, v.scale)
    return sh, d, v


def _draw_columns(d: Drawing, v: View, gm, marks: Marks, label=True):
    for c in [c for c in gm.columns if c.level == 0]:
        w, dd = _col_dims(c)
        x, y = v.p(c.x, c.y)
        pw, ph = max(v.L(w), 1.2), max(v.L(dd), 1.2)
        mk = marks.columns.get(c.id, "")
        st = marks.column_info[mk].status if mk in marks.column_info else "PASS"
        d.rect(x - pw / 2, y - ph / 2, pw, ph, lw="medium", fill=_sc(st) or "black", color=_sc(st) or "black",
               layer="COLUMNS")
        if label:
            d.text(x + pw / 2 + 0.8, y + ph / 2 + 0.6, mk, size=2.2, bold=True, color=_sc(st) or "black",
                   layer="COLUMN_MARKS")


def _schedule_rows_columns(marks: Marks):
    rows, colors = [], []
    for mk, info in marks.column_info.items():
        for k, r in enumerate(info.rows):
            rows.append([mk if k == 0 else "", str(info.count) if k == 0 else "", f"L{r['level']}", r["size"],
                         r["bars"], r["links"].split(" (")[0], format_interaction_ratio(r["ratio"]), r["status"]])
            colors.append(_sc(r["status"]))
    return rows, colors


COL_COLS = [("Mark", 11), ("Nos", 8), ("Lvl", 8), ("Size", 16), ("Bars", 15), ("Ties", 30), ("P-M", 10), ("Status", 14)]
FTG_COLS = [("Mark", 11), ("Nos", 9), ("L x B", 22), ("Depth", 12), ("Bottom steel (both ways)", 44), ("Status", 14)]
BEAM_COLS = [("Mark", 10), ("Nos", 8), ("Size", 16), ("Bottom", 17), ("Top", 17), ("Stirrups", 32), ("Status", 12)]
SLAB_COLS = [("Mark", 10), ("Nos", 8), ("Thk", 10), ("Bottom short", 22), ("Bottom long", 22), ("Top", 30), ("Status", 10)]


def _side_schedule(sheets: List[Sheet], d: Drawing, number: str, title: str, cols, rows, colors, project):
    """Put a schedule in the side panel; overflow goes to continuation sheets."""
    x, y = SIDE_PANEL[0] + 2, SIDE_PANEL[3] - 6
    n = table(d, x, y, cols, rows, title=title, row_colors=colors)
    rest, rest_c = rows[n:], colors[n:]
    page = 1
    while rest:
        sh = new_sheet(f"{number}{chr(64 + page)}", f"{title} (continued)", "-", project, side_panel=False)
        k = table(sh.drawing, BORDER[0] + 6, BORDER[3] - 8, cols, rest, title=f"{title} (continued)",
                  row_colors=rest_c, max_bottom=64.0)
        sheets.append(sh)
        rest, rest_c = rest[k:], rest_c[k:]
        page += 1
    if page > 1:
        d.text(x, SIDE_PANEL[1] + 4, f"Schedule continues on sheet(s) {number}A...", size=2.0, color="blue",
               layer="SCHEDULE")


# ------------------------------------------------------------------ sheets

def column_layout(gm, marks: Marks, project, extra_sheets: List[Sheet]) -> Sheet:
    sh, d, v = _plan_base(gm, project, "S-01", "COLUMN LAYOUT PLAN")
    _draw_columns(d, v, gm, marks)
    rows, colors = _schedule_rows_columns(marks)
    _side_schedule(extra_sheets, d, "S-01", "COLUMN SCHEDULE", COL_COLS, rows, colors, project)
    notes(d, _general_notes(gm, ["Column marks apply to the full height; schedule lists each storey (L0 = ground storey)."]))
    sh.kind = "column_layout"
    return sh


def footing_layout(gm, footings, marks: Marks, project, extra_sheets: List[Sheet]) -> Sheet:
    sh, d, v = _plan_base(gm, project, "S-02", "FOOTING LAYOUT PLAN")
    level0 = {c.id: c for c in gm.columns if c.level == 0}
    for ft in footings:
        c = level0.get(ft.id[2:])
        if c is None:
            continue
        x, y = v.p(c.x, c.y)
        L, B = v.L(ft.length_m * 1000), v.L(ft.width_m * 1000)
        mk = marks.footings.get(ft.id, "")
        col = _sc(ft.status) or "black"
        d.rect(x - L / 2, y - B / 2, L, B, lw="medium", color=col, layer="FOOTINGS")
        d.text(x, y - B / 2 - 0.8, mk, size=2.2, bold=True, halign="center", valign="top", color=col,
               layer="FOOTING_MARKS")
    _draw_columns(d, v, gm, marks, label=False)
    rows, colors = [], []
    for mk, info in marks.footing_info.items():
        r = info.rows[0]
        rows.append([mk, str(info.count), r["size"], r["depth"], r["steel"].replace(" both ways (bottom)", ""), info.status])
        colors.append(_sc(info.status))
    _side_schedule(extra_sheets, d, "S-02", "FOOTING SCHEDULE", FTG_COLS, rows, colors, project)
    notes(d, _general_notes(gm, ["Footings are concentric with the columns (centre on grid intersection).",
                                 "Founding level and SBC to be confirmed by geotechnical investigation."]))
    sh.kind = "footing_layout"
    return sh


def beam_layout(gm, beams, marks: Marks, project, extra_sheets: List[Sheet]) -> Sheet:
    levels = ", ".join(f"+{(i + 1) * gm.story_height_m:.2f}" for i in range(gm.num_stories))
    sh, d, v = _plan_base(gm, project, "S-03", "TYPICAL FLOOR BEAM & SLAB LAYOUT")
    _draw_voids(d, v, gm)
    # slab panels
    for p, (sid, s) in zip(gm.slab_panels(), gm.slab_schedule.items()):
        (x0, y0), (x1, y1) = v.p(p["x0"], p["y0"]), v.p(p["x1"], p["y1"])
        mk = marks.slabs.get(sid, "")
        d.text((x0 + x1) / 2, (y0 + y1) / 2 + 1.2, mk, size=2.4, bold=True, halign="center", valign="bottom",
               color=_sc(s.status) or "blue", layer="SLAB_MARKS")
        d.text((x0 + x1) / 2, (y0 + y1) / 2 - 1.2, f"{s.thickness_mm:.0f} THK", size=1.9, halign="center",
               valign="top", color="blue", layer="SLAB_MARKS")
    for b in beams:
        mk = marks.beams.get(b.id)
        if mk is None:
            continue
        r = gm.get_beam_result(b.id)
        (x1, y1), (x2, y2) = v.p(b.start_point.x, b.start_point.y), v.p(b.end_point.x, b.end_point.y)
        Lp = math.hypot(x2 - x1, y2 - y1)
        if Lp < 1e-6:
            continue
        ux, uy = (x2 - x1) / Lp, (y2 - y1) / Lp
        hw = max(v.L(r.width_mm), 0.8) / 2
        nx, ny = -uy * hw, ux * hw
        col = _sc(r.status) or "black"
        d.polyline([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], closed=True,
                   lw="thin", color=col, layer="BEAMS")
        ang = math.degrees(math.atan2(uy, ux))
        if ang > 90 or ang <= -90:
            ang -= 180 if ang > 0 else -180
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        off = hw + 0.8
        d.text(mx - uy * off, my + ux * off, f"{mk} ({r.width_mm:.0f}x{r.depth_mm:.0f})", size=1.8, halign="center",
               valign="bottom", rot=ang, color=col, layer="BEAM_MARKS")
    _draw_columns(d, v, gm, marks, label=False)
    rows, colors = [], []
    for mk, info in marks.beam_info.items():
        r = info.rows[0]
        rows.append([mk, str(info.count), r["size"], r["bottom"], r["top"], r["stirrups"].split(" (")[0], info.status])
        colors.append(_sc(info.status))
    _side_schedule(extra_sheets, d, "S-03", "BEAM SCHEDULE", BEAM_COLS, rows, colors, project)
    notes(d, _general_notes(gm, [f"Layout applies to all floors and roof (levels {levels} m); beams are designed for the "
                                 f"worst storey.",
                                 "Top bars continuous over supports, bottom bars continuous in span (no curtailment designed)."]))
    sh.kind = "beam_layout"
    return sh


def slab_plan(gm, marks: Marks, project, extra_sheets: List[Sheet]) -> Sheet:
    sh, d, v = _plan_base(gm, project, "S-05", "SLAB REINFORCEMENT PLAN (TYPICAL FLOOR)")
    _draw_voids(d, v, gm)
    for p, (sid, s) in zip(gm.slab_panels(), gm.slab_schedule.items()):
        (x0, y0), (x1, y1) = v.p(p["x0"], p["y0"]), v.p(p["x1"], p["y1"])
        col = _sc(s.status) or "black"
        d.rect(x0, y0, x1 - x0, y1 - y0, lw="thin", color="grey", layer="SLAB_OUTLINE")
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        short_along_x = (p["x1"] - p["x0"]) <= (p["y1"] - p["y0"])
        bx = s.main_steel_desc if short_along_x else s.dist_steel_desc
        by = s.dist_steel_desc if short_along_x else s.main_steel_desc
        # bottom bars: arrow lines in both directions
        d.line(cx - (x1 - x0) * 0.3, cy - 2.5, cx + (x1 - x0) * 0.3, cy - 2.5, lw="medium", color="blue", layer="SLAB_BOTTOM")
        d.text(cx, cy - 3.2, f"B {bx.replace('# @', ' @').replace(' c/c', '')}", size=1.7, halign="center",
               valign="top", color="blue", layer="SLAB_BOTTOM")
        d.line(cx + 2.5, cy - (y1 - y0) * 0.3, cx + 2.5, cy + (y1 - y0) * 0.3, lw="medium", color="blue", layer="SLAB_BOTTOM")
        d.text(cx + 5.0, cy + (y1 - y0) * 0.05, f"B {by.replace('# @', ' @').replace(' c/c', '')}", size=1.7,
               halign="left", valign="bottom", rot=90, color="blue", layer="SLAB_BOTTOM")
        d.text(cx - 2, cy + 2, f"{marks.slabs.get(sid, '')} {s.thickness_mm:.0f}", size=2.0, bold=True,
               halign="right", color=col, layer="SLAB_MARKS")
        # top bars over continuous edges
        nb = p["neighbours"]
        tops = dict(re.findall(r"(short|long) span (\d+# @ \d+)", s.top_steel_desc or ""))
        # short-span top bars sit over the long edges, long-span top bars over the short edges
        lr = tops.get("short" if short_along_x else "long", "")
        tb = tops.get("long" if short_along_x else "short", "")
        tl = 0.3
        if nb.get("left"):
            d.line(x0 + 1.5, cy - (y1 - y0) * tl, x0 + 1.5, cy + (y1 - y0) * tl, lw="thick", color="red", layer="SLAB_TOP")
        if nb.get("right"):
            d.line(x1 - 1.5, cy - (y1 - y0) * tl, x1 - 1.5, cy + (y1 - y0) * tl, lw="thick", color="red", layer="SLAB_TOP")
            if lr:
                d.text(x1, cy + (y1 - y0) * tl + 0.8, f"T {lr.replace('# @', ' @')}", size=1.5, halign="center",
                       valign="bottom", color="red", layer="SLAB_TOP")
        if nb.get("bottom"):
            d.line(cx - (x1 - x0) * tl, y0 + 1.5, cx + (x1 - x0) * tl, y0 + 1.5, lw="thick", color="red", layer="SLAB_TOP")
        if nb.get("top"):
            d.line(cx - (x1 - x0) * tl, y1 - 1.5, cx + (x1 - x0) * tl, y1 - 1.5, lw="thick", color="red", layer="SLAB_TOP")
            if tb:
                d.text(cx + (x1 - x0) * tl + 0.8, y1, f"T {tb.replace('# @', ' @')}", size=1.5, halign="left",
                       valign="middle", color="red", layer="SLAB_TOP")
    rows, colors = [], []
    for mk, info in marks.slab_info.items():
        r = info.rows[0]
        rows.append([mk, str(info.count), r["thk"], r["main"].replace(" c/c", ""), r["dist"].replace(" c/c", ""),
                     r["top"].replace("short span ", "S ").replace("long span ", "L ").replace(" c/c", ""), info.status])
        colors.append(_sc(info.status))
    _side_schedule(extra_sheets, d, "S-05", "SLAB SCHEDULE", SLAB_COLS, rows, colors, project)
    notes(d, _general_notes(gm, ["Blue: bottom bars (B). Red bars at panel edges: top bars over continuous supports, "
                                 "extending 0.3 x short span into each panel (typical).",
                                 "Corner torsion reinforcement per IS 456 Annex D is not detailed (typical detail required)."]))
    sh.kind = "slab_plan"
    return sh


# ---------------------------------------------------------------- sections

def _section_cells(n_per_row=4, cell_w=95.0, cell_h=72.0):
    x0, y_top = BORDER[0] + 5, BORDER[3] - 4
    rows = []
    for r in range(3):
        for c in range(n_per_row):
            rows.append((x0 + c * cell_w, y_top - (r + 1) * cell_h, cell_w, cell_h))
    return rows


def _detail_scale(b: float, D: float, cell_h: float = 72.0) -> float:
    return 10.0 if max(b, D) / 10.0 <= cell_h * 0.70 and b / 10.0 <= 40 else 20.0


def _column_detail(d: Drawing, cell, info, c, gm, scale=None):
    from ..section_design import column_section
    x, y, w, h = cell
    scale = scale or _detail_scale(c.width_nb, c.depth_nb, h)
    r0 = info.rows[0]
    n, dia = _bars(r0["bars"], (8, 16))
    b, D = c.width_nb, c.depth_nb
    cx, cy = x + w * 0.42, y + h * 0.52
    pb, pd = b / scale, D / scale
    col = _sc(info.status) or "black"
    d.rect(cx - pb / 2, cy - pd / 2, pb, pd, lw="heavy", color=col, layer="SECTIONS")
    cov = (40 + 4) / scale
    d.rect(cx - pb / 2 + cov, cy - pd / 2 + cov, pb - 2 * cov, pd - 2 * cov, lw="medium", layer="SECTIONS")
    sec = column_section(b, D, n, dia, gm.fck, gm.fy)
    for bx, by in zip(sec.bar_x, sec.bar_y):
        d.circle(cx + bx / scale, cy + by / scale, max(dia / 2 / scale, 0.45), lw="thin", fill="black", layer="SECTIONS")
    # dimensions
    d.line(cx - pb / 2, cy - pd / 2 - 3, cx + pb / 2, cy - pd / 2 - 3, lw="thin", layer="DIMENSIONS")
    d.text(cx, cy - pd / 2 - 3.6, f"{b:.0f}", size=1.8, halign="center", valign="top", layer="DIMENSIONS")
    d.line(cx - pb / 2 - 3, cy - pd / 2, cx - pb / 2 - 3, cy + pd / 2, lw="thin", layer="DIMENSIONS")
    d.text(cx - pb / 2 - 3.6, cy, f"{D:.0f}", size=1.8, halign="center", valign="bottom", rot=90, layer="DIMENSIONS")
    d.text(x + 3, y + h - 4, f"{info.mark}  ({info.count} Nos)", size=3.0, bold=True, color=col, layer="SECTIONS")
    lines = [f"Size {b:.0f} x {D:.0f}", f"Main {r0['bars']}"]
    for r in info.rows:
        lines.append(f"L{r['level']}: {r['bars']}, ties {r['links'].split(' (')[0]}")
    lines.append("Cover 40 clear")
    yy = y + h - 9
    for s in lines[:7]:
        d.text(cx + pb / 2 + 4, yy, s, size=1.8, layer="SECTIONS")
        yy -= 3.0
    d.text(x + 3, y + 3, f"SECTION {info.mark}   1:{scale:.0f}", size=2.0, bold=True, layer="SECTIONS")


def _beam_detail(d: Drawing, cell, info, scale=None):
    x, y, w, h = cell
    r = info.rows[0]
    b, D = (float(v) for v in r["size"].split("x"))
    scale = scale or _detail_scale(b, D, h)
    nb, db = _bars(r["bottom"], (2, 12))
    nt, dt = _bars(r["top"], (2, 12))
    cx, cy = x + w * 0.35, y + h * 0.5
    pb, pd = b / scale, D / scale
    col = _sc(info.status) or "black"
    d.rect(cx - pb / 2, cy - pd / 2, pb, pd, lw="heavy", color=col, layer="SECTIONS")
    cov = (25 + 4) / scale
    d.rect(cx - pb / 2 + cov, cy - pd / 2 + cov, pb - 2 * cov, pd - 2 * cov, lw="medium", layer="SECTIONS")
    edge = (25 + 8) / scale

    def row(nn, dia, yrow):
        if nn <= 0:
            return
        xs = [cx - pb / 2 + edge + dia / 2 / scale + i * (pb - 2 * edge - dia / scale) / max(nn - 1, 1)
              for i in range(nn)] if nn > 1 else [cx]
        for bx in xs:
            d.circle(bx, yrow, max(dia / 2 / scale, 0.45), lw="thin", fill="black", layer="SECTIONS")
    row(nt, dt, cy + pd / 2 - edge - dt / 2 / scale)
    row(nb, db, cy - pd / 2 + edge + db / 2 / scale)
    d.line(cx - pb / 2, cy - pd / 2 - 3, cx + pb / 2, cy - pd / 2 - 3, lw="thin", layer="DIMENSIONS")
    d.text(cx, cy - pd / 2 - 3.6, f"{b:.0f}", size=1.8, halign="center", valign="top", layer="DIMENSIONS")
    d.line(cx - pb / 2 - 3, cy - pd / 2, cx - pb / 2 - 3, cy + pd / 2, lw="thin", layer="DIMENSIONS")
    d.text(cx - pb / 2 - 3.6, cy, f"{D:.0f}", size=1.8, halign="center", valign="bottom", rot=90, layer="DIMENSIONS")
    d.text(x + 3, y + h - 4, f"{info.mark}  ({info.count} Nos)", size=3.0, bold=True, color=col, layer="SECTIONS")
    yy = y + h - 9
    for s in [f"Size {b:.0f} x {D:.0f}", f"Top {r['top']}", f"Bottom {r['bottom']}",
              f"Stirrups {r['stirrups'].split(' (')[0]}", (r["stirrups"].split(" (")[1].rstrip(")") if " (" in r["stirrups"] else ""),
              "Cover 25 clear", "Same bars at support and mid-span"]:
        if s:
            d.text(cx + pb / 2 + 4, yy, s, size=1.8, layer="SECTIONS")
            yy -= 3.0
    d.text(x + 3, y + 3, f"SECTION {info.mark}   1:{scale:.0f}", size=2.0, bold=True, layer="SECTIONS")


def sections_sheets(gm, beams, marks: Marks, project) -> List[Sheet]:
    items = []
    first_seg = {}
    for c in sorted(gm.columns, key=lambda c: c.level):
        first_seg.setdefault(marks.columns.get(c.id), c)
    for mk, info in marks.column_info.items():
        items.append(("col", info, first_seg.get(mk)))
    for mk, info in marks.beam_info.items():
        items.append(("beam", info, None))
    out = []
    cells = _section_cells()
    for page in range(0, max(len(items), 1), len(cells)):
        num = "S-04" if page == 0 else f"S-04{chr(64 + page // len(cells))}"
        sh = new_sheet(num, "COLUMN & BEAM SECTIONS", "1:10 / 1:20 (as noted)", project, side_panel=False)
        d = sh.drawing
        for cell, (kind, info, c) in zip(cells, items[page:page + len(cells)]):
            d.rect(*cell, lw="thin", color="lightgrey", layer="FRAMES")
            if kind == "col":
                _column_detail(d, cell, info, c, gm)
            else:
                _beam_detail(d, cell, info)
        notes(d, _general_notes(gm), area=(25.0, 12.0, 275.0, 34.0))
        sh.kind = "sections"
        out.append(sh)
    return out


def footing_sections(gm, footings, marks: Marks, project) -> List[Sheet]:
    infos = list(marks.footing_info.values())
    biggest = max((f.length_m for f in footings), default=1.5) * 1000
    scale = next(s for s in (20, 25, 50, 75, 100) if biggest / s <= 80)
    out = []
    cells = _section_cells(n_per_row=3, cell_w=126.0)
    by_id = {f.id: f for f in footings}
    level0 = {c.id: c for c in gm.columns if c.level == 0}
    for page in range(0, max(len(infos), 1), len(cells)):
        num = "S-06" if page == 0 else f"S-06{chr(64 + page // len(cells))}"
        sh = new_sheet(num, "FOOTING SECTIONS", f"1:{scale}", project, side_panel=False)
        d = sh.drawing
        for cell, info in zip(cells, infos[page:page + len(cells)]):
            ft = by_id[info.members[0]]
            c = level0.get(ft.id[2:])
            x, y, w, h = cell
            d.rect(*cell, lw="thin", color="lightgrey", layer="FRAMES")
            col = _sc(info.status) or "black"
            L, T = ft.length_m * 1000 / scale, ft.thickness_mm / scale
            cx, base = x + w * 0.4, y + h * 0.3
            d.rect(cx - L / 2, base - 75 / scale, L, 75 / scale, lw="thin", ltype="dashed", color="grey", layer="SECTIONS")
            d.rect(cx - L / 2, base, L, T, lw="heavy", color=col, layer="SECTIONS")
            cw = (c.width_nb if c else 300) / scale
            d.rect(cx - cw / 2, base + T, cw, 600 / scale, lw="medium", layer="SECTIONS")
            d.line(cx - cw / 2 + 48 / scale, base + 50 / scale, cx - cw / 2 + 48 / scale, base + T + 600 / scale,
                   lw="thin", layer="SECTIONS")
            d.line(cx + cw / 2 - 48 / scale, base + 50 / scale, cx + cw / 2 - 48 / scale, base + T + 600 / scale,
                   lw="thin", layer="SECTIONS")
            sp = _spacing(ft.rebar_desc) or 200
            nb = max(2, int((ft.length_m * 1000 - 100) // sp) + 1)
            bar_y = base + 56 / scale
            d.line(cx - L / 2 + 50 / scale, bar_y, cx + L / 2 - 50 / scale, bar_y, lw="medium", layer="SECTIONS")
            for i in range(nb):
                bx = cx - L / 2 + 50 / scale + i * (L - 100 / scale) / max(nb - 1, 1)
                d.circle(bx, bar_y + 12 / scale, max(6 / scale, 0.4), lw="thin", fill="black", layer="SECTIONS")
            d.line(cx - L / 2, base - 75 / scale - 3, cx + L / 2, base - 75 / scale - 3, lw="thin", layer="DIMENSIONS")
            d.text(cx, base - 75 / scale - 3.6, f"{ft.length_m * 1000:.0f}", size=1.8, halign="center", valign="top",
                   layer="DIMENSIONS")
            d.text(cx + L / 2 + 1.5, base + T / 2, f"{ft.thickness_mm:.0f}", size=1.8, valign="middle", layer="DIMENSIONS")
            d.text(x + 3, y + h - 4, f"{info.mark}  ({info.count} Nos)", size=3.0, bold=True, color=col, layer="SECTIONS")
            yy = y + h - 9
            for s in [f"{ft.length_m * 1000:.0f} x {ft.width_m * 1000:.0f} x {ft.thickness_mm:.0f} deep",
                      f"Bottom {ft.rebar_desc}", "Cover 50 clear", "Column starter bars as column schedule",
                      "PCC 75 thk below (typical, not designed)"] + [f"! {wn}" for wn in ft.warnings][:2]:
                d.text(x + w * 0.62, yy, s[:48], size=1.7, color="orange" if s.startswith("!") else "black", layer="SECTIONS")
                yy -= 3.0
            d.text(x + 3, y + 3, f"SECTION {info.mark}   1:{scale}", size=2.0, bold=True, layer="SECTIONS")
        notes(d, _general_notes(gm), area=(25.0, 12.0, 275.0, 34.0))
        sh.kind = "footing_sections"
        out.append(sh)
    return out


def build_drawing_set(gm, beams, footings, project: Dict[str, str]) -> List[Sheet]:
    """All sheets for a designed model, in sheet-number order."""
    marks = compute_marks(gm, beams, footings)
    extra: List[Sheet] = []
    sheets = [column_layout(gm, marks, project, extra),
              footing_layout(gm, footings, marks, project, extra),
              beam_layout(gm, beams, marks, project, extra)]
    sheets += sections_sheets(gm, beams, marks, project)
    sheets.append(slab_plan(gm, marks, project, extra))
    sheets += footing_sections(gm, footings, marks, project)
    sheets += extra
    return sorted(sheets, key=lambda s: s.number)
