"""
Generator for DXF plans drawn the way real offices draw them (test helper, not a test module).

The plan is a 4 x 3 bay RC frame: x grid 0 / 4.5 / 9 / 13.5 / 18 m, y grid 0 / 4 / 8 / 12 m, 20 columns of
300 (x) x 450 (y) mm, 31 beams along the grid lines, 230 mm walls on the perimeter. On top of that it adds what a
real drawing carries: grid lines with bubbles, column tags and leaders, dimensions, door blocks and hatches.

Options reproduce real conventions and drafting habits:
- layer naming: ``ncs`` (US National CAD Standard / AIA: S-COLS, S-BEAM, A-WALL, S-GRID ...), ``ncs_long``
  (S-COLS-CONC ...), ``indian`` (COLUMN, BEAM, WALL, CENTRE LINE, ...);
- column drawing: closed ``lwpoly``, old 2D ``polyline``, ``block`` inserts (geometry on layer 0 inside the block,
  the INSERT on the column layer), ``block_rotated`` (block of 450 x 300 inserted at 90 degrees), ``circle``;
- ``nest``: the whole plan inside one block inserted once (a bound xref);
- ``units``: "mm" ($INSUNITS 4), "cm" (5), "m" (6) or "none" ($INSUNITS 0, millimetre coordinates);
- ``offset``: survey coordinates (metres, added to every point); ``jitter``: drafting misalignment (m, random,
  seeded); ``duplicate_columns``: every column outline drawn twice; ``beam_style``: "line", "lwpoly" (one polyline
  per grid line), "to_face" (lines stopping at the column faces);
- ``dxfversion``: "R2018" or "R12";
- ``layer_names``: override any layer name of the convention (e.g. ``{"col": "Layer 7"}``, or every key "0" for a
  drawing with everything on one layer).
"""
import random
from typing import Optional

import ezdxf

X = [0.0, 4.5, 9.0, 13.5, 18.0]
Y = [0.0, 4.0, 8.0, 12.0]
COL_B, COL_D = 0.300, 0.450      # m, along x and y
N_COLUMNS = len(X) * len(Y)
N_BEAMS = (len(X) - 1) * len(Y) + (len(Y) - 1) * len(X)

LAYERS = {
    "ncs": dict(col="S-COLS", beam="S-BEAM", wall="A-WALL", grid="S-GRID", grid_iden="S-GRID-IDEN",
                col_iden="S-COLS-IDEN", dims="A-ANNO-DIMS", door="A-DOOR", hatch="A-WALL-PATT"),
    "ncs_long": dict(col="S-COLS-CONC", beam="S-BEAM-CONC", wall="A-WALL-FULL", grid="S-GRID", grid_iden="S-GRID-IDEN",
                     col_iden="S-COLS-IDEN", dims="A-ANNO-DIMS", door="A-DOOR", hatch="A-WALL-PATT"),
    "indian": dict(col="COLUMN", beam="BEAM", wall="WALL", grid="CENTRE LINE", grid_iden="GRID TEXT",
                   col_iden="COL TEXT", dims="DIMENSION", door="DOOR", hatch="HATCH"),
}
UNIT = {"mm": (1000.0, 4), "cm": (100.0, 5), "m": (1.0, 6), "none": (1000.0, 0)}


def make_plan(path, *, layers: str = "ncs", units: str = "mm", columns: str = "lwpoly", nest: bool = False,
              offset=(0.0, 0.0), jitter: float = 0.0, duplicate_columns: bool = False, beam_style: str = "line",
              dxfversion: str = "R2018", extra_column_layers: Optional[list] = None, seed: int = 7,
              layer_names: Optional[dict] = None) -> str:
    rnd = random.Random(seed)
    f, code = UNIT[units]
    L = dict(LAYERS[layers], **(layer_names or {}))
    doc = ezdxf.new(dxfversion)
    doc.header["$INSUNITS"] = code
    for name in set(L.values()):
        if name not in doc.layers:
            doc.layers.add(name)

    def p(x, y):
        return ((x + offset[0]) * f, (y + offset[1]) * f)

    plan = doc.blocks.new("PLAN-XREF") if nest else doc.modelspace()

    # column block definitions (geometry on layer 0, inherits the INSERT's layer)
    if columns.startswith("block"):
        blk = doc.blocks.new("COL_300X450")
        hb, hd = COL_B / 2 * f, COL_D / 2 * f
        _rect(blk, -hb, -hd, hb, hd, "0", dxfversion)
        blk90 = doc.blocks.new("COL_450X300")
        _rect(blk90, -hd, -hb, hd, hb, "0", dxfversion)

    centres = []
    for x in X:
        for y in Y:
            jx, jy = (rnd.uniform(-jitter, jitter), rnd.uniform(-jitter, jitter)) if jitter else (0.0, 0.0)
            centres.append((x + jx, y + jy))

    for i, (x, y) in enumerate(centres):
        cx, cy = p(x, y)
        hb, hd = COL_B / 2 * f, COL_D / 2 * f
        for _ in range(2 if duplicate_columns else 1):
            if columns == "lwpoly":
                _rect(plan, cx - hb, cy - hd, cx + hb, cy + hd, L["col"], dxfversion)
            elif columns == "polyline":
                plan.add_polyline2d([(cx - hb, cy - hd), (cx + hb, cy - hd), (cx + hb, cy + hd), (cx - hb, cy + hd)],
                                    close=True, dxfattribs={"layer": L["col"]})
            elif columns == "block":
                plan.add_blockref("COL_300X450", (cx, cy), dxfattribs={"layer": L["col"]})
            elif columns == "block_rotated":
                # a 450 (x) x 300 (y) block rotated 90 degrees -> 300 (x) x 450 (y) on plan
                plan.add_blockref("COL_450X300", (cx, cy), dxfattribs={"layer": L["col"], "rotation": 90.0})
            elif columns == "circle":
                plan.add_circle((cx, cy), 0.225 * f, dxfattribs={"layer": L["col"]})
        # column tag with a leader (open polyline) on the identification layer
        plan.add_text(f"C{i + 1}", dxfattribs={"layer": L["col_iden"], "height": 0.15 * f}).set_placement(
            (cx + 0.3 * f, cy + 0.3 * f))
        _open_poly(plan, [(cx + 0.15 * f, cy + 0.15 * f), (cx + 0.3 * f, cy + 0.3 * f), (cx + 0.6 * f, cy + 0.3 * f)],
                   L["col_iden"], dxfversion)

    for name in extra_column_layers or []:      # look-alike layers that are not columns
        doc.layers.add(name)
        _rect(plan, *p(2.0, 2.0), *p(2.6, 2.6), name, dxfversion)

    # beams along the grid lines
    by_xy = {(round(x, 3), round(y, 3)): c for (x, y), c in zip([(x, y) for x in X for y in Y], centres)}
    for y in Y:
        pts = [by_xy[(round(x, 3), round(y, 3))] for x in X]
        _beam_run(plan, pts, "x", L["beam"], beam_style, p, f, dxfversion)
    for x in X:
        pts = [by_xy[(round(x, 3), round(y, 3))] for y in Y]
        _beam_run(plan, pts, "y", L["beam"], beam_style, p, f, dxfversion)

    # perimeter walls: two lines 230 mm apart, centred on the outer grid lines
    t = 0.115
    for (x1, y1, x2, y2) in [(X[0], Y[0], X[-1], Y[0]), (X[-1], Y[0], X[-1], Y[-1]), (X[-1], Y[-1], X[0], Y[-1]),
                             (X[0], Y[-1], X[0], Y[0])]:
        dx, dy = (0, t) if y1 == y2 else (t, 0)
        plan.add_line(p(x1 - dx, y1 - dy), p(x2 - dx, y2 - dy), dxfattribs={"layer": L["wall"]})
        plan.add_line(p(x1 + dx, y1 + dy), p(x2 + dx, y2 + dy), dxfattribs={"layer": L["wall"]})

    # grid lines extending 1.5 m beyond the building with bubbles (circles + text)
    for i, x in enumerate(X):
        plan.add_line(p(x, Y[0] - 1.5), p(x, Y[-1] + 1.5), dxfattribs={"layer": L["grid"]})
        plan.add_circle(p(x, Y[-1] + 1.9), 0.4 * f, dxfattribs={"layer": L["grid_iden"]})
        plan.add_text("ABCDE"[i], dxfattribs={"layer": L["grid_iden"], "height": 0.3 * f}).set_placement(
            p(x, Y[-1] + 1.9))
    for j, y in enumerate(Y):
        plan.add_line(p(X[0] - 1.5, y), p(X[-1] + 1.5, y), dxfattribs={"layer": L["grid"]})
        plan.add_circle(p(X[0] - 1.9, y), 0.4 * f, dxfattribs={"layer": L["grid_iden"]})

    # dimensions and a door block
    if dxfversion != "R12":
        dim = plan.add_linear_dim(base=p(0, -1.0), p1=p(0, 0), p2=p(4.5, 0), dxfattribs={"layer": L["dims"]})
        dim.render()
    door = doc.blocks.new("DOOR-900")
    door.add_line((0, 0), (0.9 * f, 0), dxfattribs={"layer": "0"})
    door.add_arc((0, 0), 0.9 * f, 0, 90, dxfattribs={"layer": "0"})
    plan.add_blockref("DOOR-900", p(2.0, -0.115), dxfattribs={"layer": L["door"]})

    if nest:
        doc.modelspace().add_blockref("PLAN-XREF", (0, 0), dxfattribs={"layer": "0"})
    doc.saveas(path)
    return str(path)


def _rect(target, x0, y0, x1, y1, layer, dxfversion):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if dxfversion == "R12":
        target.add_polyline2d(pts, close=True, dxfattribs={"layer": layer})
    else:
        target.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def _open_poly(target, pts, layer, dxfversion):
    if dxfversion == "R12":
        target.add_polyline2d(pts, dxfattribs={"layer": layer})
    else:
        target.add_lwpolyline(pts, dxfattribs={"layer": layer})


def _beam_run(target, centres, axis, layer, style, p, f, dxfversion):
    if style == "lwpoly" and dxfversion != "R12":
        target.add_lwpolyline([p(*c) for c in centres], dxfattribs={"layer": layer})
        return
    for a, b in zip(centres, centres[1:]):
        if style == "to_face":     # drawn from column face to column face
            half = (COL_B if axis == "x" else COL_D) / 2
            if axis == "x":
                a, b = (a[0] + half, a[1]), (b[0] - half, b[1])
            else:
                a, b = (a[0], a[1] + half), (b[0], b[1] - half)
        target.add_line(p(*a), p(*b), dxfattribs={"layer": layer})
