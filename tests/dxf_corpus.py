"""
A corpus of DXF building plans drawn in many different ways (test helper, not a test module).

``CASES`` maps a case name to a spec; ``make(path, spec)`` draws it. Every spec describes a building StructOptima is
meant to read (orthogonal RC frame: columns, beams on the grid lines, walls) or a drawing that is valid DXF but has
no usable structure (it must give a clear input error). What varies:

- plan shape (rect, L, T, U, courtyard, cross, irregular, single bay, single line of bays, one column), number of bays
  and bay sizes (2.5 - 12 m, mixed), large floor plates (mall: 12 x 9 bays);
- units ($INSUNITS mm / cm / m / inch / feet / none), survey offsets, the whole plan rotated (0 / 90 / 180 / 270 or an
  arbitrary angle) or mirrored;
- columns: closed LWPOLYLINE, old POLYLINE, blocks (plain, rotated, scaled, mirrored, nested two deep), circles,
  mixed, duplicated, sizes 230 - 600 mm, the size varying column to column;
- beams: one LINE per bay, one polyline per grid line, lines stopping at column faces, missing beams, no beams at all,
  cantilever beams beyond the last column;
- walls: none, perimeter double lines, interior partitions, walls only (no columns: automatic column placement);
- noise: grid lines and bubbles, text, MTEXT, dimensions, hatches, arcs, ellipses, splines, points, XLINE / RAY
  (infinite construction lines), title block far away on an annotation layer, entities in paper space;
- layer names: NCS, Indian, random, everything on layer 0;
- DXF versions R12, R2000, R2010, R2018.

Expected results are not taken from the application: a case only states what must hold whatever the numbers are
(clear input error or a design that satisfies tests/invariants.py, no crash, bounded time and memory), plus, for
the orthogonal cases, the number of columns drawn (``spec["n_columns"]`` after ``make``).
"""
import math
import random
from typing import Dict, List, Tuple

import ezdxf

UNITS = {"mm": (1000.0, 4), "cm": (100.0, 5), "m": (1.0, 6), "in": (1 / 0.0254, 1), "ft": (1 / 0.3048, 2),
         "none": (1000.0, 0)}
LAYER_SETS = {
    "ncs": dict(col="S-COLS", beam="S-BEAM", wall="A-WALL", grid="S-GRID", text="A-ANNO-TEXT", dims="A-ANNO-DIMS",
                hatch="A-WALL-PATT", title="A-ANNO-TTLB"),
    "indian": dict(col="COLUMN", beam="BEAM", wall="WALL", grid="CENTRE LINE", text="TEXT", dims="DIMENSION",
                   hatch="HATCH", title="TITLE BLOCK"),
    "zero": {k: "0" for k in ("col", "beam", "wall", "grid", "text", "dims", "hatch", "title")},
}


def _cells(shape: str, nx: int, ny: int, rnd: random.Random) -> set:
    """Bays (i, j) that are part of the building."""
    allc = {(i, j) for i in range(nx) for j in range(ny)}
    if shape == "rect" or nx < 2 or ny < 2:
        return allc
    if shape == "L":
        return {(i, j) for (i, j) in allc if i < max(1, nx // 2) or j < max(1, ny // 2)}
    if shape == "T":
        return {(i, j) for (i, j) in allc if j >= ny - max(1, ny // 3) or nx // 3 <= i < nx - nx // 3}
    if shape == "U":
        return {(i, j) for (i, j) in allc if j < max(1, ny // 3) or i < max(1, nx // 3) or i >= nx - max(1, nx // 3)}
    if shape == "courtyard" and nx >= 3 and ny >= 3:
        return allc - {(nx // 2, ny // 2)}
    if shape == "cross" and nx >= 3 and ny >= 3:
        return {(i, j) for (i, j) in allc if nx // 3 <= i < nx - nx // 3 or ny // 3 <= j < ny - ny // 3}
    if shape == "irregular":
        keep = set(allc)
        for c in rnd.sample(sorted(allc), max(1, len(allc) // 4)):
            trial = keep - {c}
            if trial and _connected(trial):
                keep = trial
        return keep
    return allc


def _connected(cells: set) -> bool:
    start = next(iter(cells))
    seen, todo = {start}, [start]
    while todo:
        i, j = todo.pop()
        for n in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if n in cells and n not in seen:
                seen.add(n)
                todo.append(n)
    return len(seen) == len(cells)


def make(path, spec: Dict) -> str:
    """Draw ``spec`` (see CASES) into ``path``; sets spec["n_columns"] (columns drawn, None for walls-only)."""
    rnd = random.Random(spec.get("seed", 1))
    f, code = UNITS[spec.get("units", "mm")]
    if spec.get("layers") == "random":
        L = {k: "".join(rnd.choice("ABCDEFGHJK0123456789-_") for _ in range(6)) for k in LAYER_SETS["ncs"]}
    else:
        L = dict(LAYER_SETS[spec.get("layers", "ncs")])
    version = spec.get("version", "R2018")
    doc = ezdxf.new(version)
    doc.header["$INSUNITS"] = code
    for name in set(L.values()):
        if name not in doc.layers:
            doc.layers.add(name)
    msp = doc.modelspace()

    xs = [0.0]
    for _ in range(spec.get("nx", 3)):
        xs.append(xs[-1] + (spec["bay"] if "bay" in spec else rnd.choice(spec.get("bays", [4.0]))))
    ys = [0.0]
    for _ in range(spec.get("ny", 2)):
        ys.append(ys[-1] + (spec["bay_y"] if "bay_y" in spec else rnd.choice(spec.get("bays", [4.0]))))
    cells = _cells(spec.get("shape", "rect"), len(xs) - 1, len(ys) - 1, rnd)
    nodes = sorted({(i + a, j + b) for (i, j) in cells for a in (0, 1) for b in (0, 1)})
    if spec.get("single_column"):
        nodes = [(0, 0)]
    if spec.get("two_columns"):
        nodes = [(0, 0), (1, 0)]
    if spec.get("three_columns"):
        nodes = [(0, 0), (1, 0), (0, 1)]
    if spec.get("row"):
        nodes = [(i, 0) for i in range(len(xs))]

    ang = math.radians(spec.get("rotate", 0.0))
    ox, oy = spec.get("offset", (0.0, 0.0))
    mirror = -1.0 if spec.get("mirror") else 1.0

    def P(x, y):                                      # metres on plan -> drawing units
        x *= mirror
        xr, yr = x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang)
        return ((xr + ox) * f, (yr + oy) * f)

    target = msp
    if spec.get("nest"):
        target = doc.blocks.new("PLAN")

    # ---- columns ----
    style = spec.get("columns", "lwpoly")
    sizes = spec.get("col_sizes", [(0.30, 0.45)])
    n_cols = 0
    if style != "none":
        if style.startswith("block") or style == "mixed":
            for k, (b, d) in enumerate(sizes):
                blk = doc.blocks.new(f"COL{k}")
                _rect(blk, [(-b / 2 * f, -d / 2 * f), (b / 2 * f, -d / 2 * f), (b / 2 * f, d / 2 * f),
                            (-b / 2 * f, d / 2 * f)], "0", version)
            if style == "block_nested":
                outer = doc.blocks.new("COLWRAP")
                outer.add_blockref("COL0", (0, 0), dxfattribs={"layer": "0"})
        for n, (i, j) in enumerate(nodes):
            x, y = xs[i], ys[j]
            b, d = sizes[n % len(sizes)] if spec.get("vary_sizes") else sizes[0]
            kind = style if style != "mixed" else ["lwpoly", "polyline", "block", "circle"][n % 4]
            cx, cy = P(x, y)
            reps = 2 if spec.get("duplicate_columns") else 1
            for _ in range(reps):
                if kind == "lwpoly" or (kind == "polyline"):
                    corners = [P(x - b / 2 * mirror, y - d / 2), P(x + b / 2 * mirror, y - d / 2),
                               P(x + b / 2 * mirror, y + d / 2), P(x - b / 2 * mirror, y + d / 2)]
                    if kind == "polyline" or version == "R12":
                        target.add_polyline2d(corners, close=True, dxfattribs={"layer": L["col"]})
                    else:
                        target.add_lwpolyline(corners, close=True, dxfattribs={"layer": L["col"]})
                elif kind == "circle":
                    target.add_circle((cx, cy), 0.5 * math.sqrt(b * d * 4 / math.pi) * f,
                                      dxfattribs={"layer": L["col"]})
                elif kind in ("block", "block_rotated", "block_scaled", "block_mirrored", "block_nested"):
                    k = sizes.index((b, d)) if (b, d) in sizes else 0
                    attrs = {"layer": L["col"], "rotation": spec.get("rotate", 0.0)}
                    name = f"COL{k}"
                    if kind == "block_scaled":                 # block drawn in metres, inserted x f
                        blk = doc.blocks.get(f"COLM{k}") or doc.blocks.new(f"COLM{k}")
                        if not len(blk):
                            _rect(blk, [(-b / 2, -d / 2), (b / 2, -d / 2), (b / 2, d / 2), (-b / 2, d / 2)], "0",
                                  version)
                        name = f"COLM{k}"
                        attrs.update(xscale=f, yscale=f)
                    if kind == "block_mirrored":
                        attrs["xscale"] = -1.0
                    if kind == "block_nested":
                        name = "COLWRAP"
                    target.add_blockref(name, (cx, cy), dxfattribs=attrs)
            n_cols += 1
    spec["n_columns"] = n_cols if style != "none" else None

    # ---- beams ----
    beam_style = spec.get("beams", "line")
    edges = []
    nodeset = set(nodes)
    for (i, j) in nodes:
        if (i + 1, j) in nodeset and ((i, j) in cells or (i, j - 1) in cells):
            edges.append(((i, j), (i + 1, j)))
        if (i, j + 1) in nodeset and ((i, j) in cells or (i - 1, j) in cells):
            edges.append(((i, j), (i, j + 1)))
    if spec.get("row"):
        edges = [((i, 0), (i + 1, 0)) for i in range(len(xs) - 1)]
    elif spec.get("single_column") or spec.get("two_columns") or spec.get("three_columns"):
        edges = {"two_columns": [((0, 0), (1, 0))], "three_columns": [((0, 0), (1, 0)), ((0, 0), (0, 1))]}.get(
            next((k for k in ("two_columns", "three_columns") if spec.get(k)), ""), [])
    if beam_style == "missing_some":
        edges = [e for k, e in enumerate(edges) if k % 5]
    if beam_style not in ("none",):
        for a, b2 in edges:
            (x1, y1), (x2, y2) = (xs[a[0]], ys[a[1]]), (xs[b2[0]], ys[b2[1]])
            if beam_style == "to_face":
                hx = 0.15 if y1 == y2 else 0.0
                hy = 0.225 if x1 == x2 else 0.0
                x1, y1, x2, y2 = x1 + hx, y1 + hy, x2 - hx, y2 - hy
            if beam_style == "lwpoly" and version != "R12":
                target.add_lwpolyline([P(x1, y1), P(x2, y2)], dxfattribs={"layer": L["beam"]})
            else:
                target.add_line(P(x1, y1), P(x2, y2), dxfattribs={"layer": L["beam"]})
            if beam_style == "zero_length_extra":
                target.add_line(P(x1, y1), P(x1, y1), dxfattribs={"layer": L["beam"]})
        if spec.get("cantilever") and nodes:
            i, j = max(nodes)
            target.add_line(P(xs[i], ys[j]), P(xs[i] + 1.5, ys[j]), dxfattribs={"layer": L["beam"]})

    # ---- walls ----
    walls = spec.get("walls", "perimeter")
    if walls in ("perimeter", "interior", "only"):
        t = 0.115
        segs = []
        for (a, b2) in edges or [((i, j), (i + 1, j)) for (i, j) in nodes if (i + 1, j) in nodeset]:
            (x1, y1), (x2, y2) = (xs[a[0]], ys[a[1]]), (xs[b2[0]], ys[b2[1]])
            inside = sum(1 for c in _adjacent_cells(a, b2) if c in cells)
            if walls == "perimeter" and inside != 1:
                continue
            segs.append((x1, y1, x2, y2))
        for (x1, y1, x2, y2) in segs:
            dx, dy = (0.0, t) if y1 == y2 else (t, 0.0)
            target.add_line(P(x1 - dx, y1 - dy), P(x2 - dx, y2 - dy), dxfattribs={"layer": L["wall"]})
            target.add_line(P(x1 + dx, y1 + dy), P(x2 + dx, y2 + dy), dxfattribs={"layer": L["wall"]})

    # ---- annotation and noise ----
    if spec.get("noise", True):
        for i, x in enumerate(xs):
            target.add_line(P(x, ys[0] - 1.5), P(x, ys[-1] + 1.5), dxfattribs={"layer": L["grid"]})
            target.add_circle(P(x, ys[-1] + 1.9), 0.4 * f, dxfattribs={"layer": L["grid"]})
        target.add_text("GROUND FLOOR PLAN", dxfattribs={"layer": L["text"], "height": 0.3 * f}).set_placement(
            P(xs[0], ys[0] - 3.0))
        target.add_arc(P(xs[0] + 1.0, ys[0]), 0.9 * f, 0, 90, dxfattribs={"layer": L["text"]})
        if version != "R12":
            target.add_mtext("NOTES:\\PALL DIMENSIONS IN MM", dxfattribs={"layer": L["text"]}).set_location(
                P(xs[-1] + 3.0, ys[-1]))
            target.add_ellipse(P(xs[0] + 2.0, ys[0] + 2.0), major_axis=(0.5 * f, 0, 0), ratio=0.5,
                               dxfattribs={"layer": L["text"]})
            target.add_spline([P(xs[0], ys[0]) + (0,), P(xs[0] + 1, ys[0] + 0.5) + (0,),
                               P(xs[0] + 2, ys[0]) + (0,)], dxfattribs={"layer": L["text"]})
            h = target.add_hatch(dxfattribs={"layer": L["hatch"]})
            h.paths.add_polyline_path([P(xs[0], ys[0]), P(xs[0] + 0.5, ys[0]), P(xs[0] + 0.5, ys[0] + 0.5)],
                                      is_closed=True)
            dim = target.add_linear_dim(base=P(xs[0], ys[0] - 1.0), p1=P(xs[0], ys[0]), p2=P(xs[1], ys[0]),
                                        dxfattribs={"layer": L["dims"]})
            dim.render()
            target.add_point(P(xs[0], ys[0]), dxfattribs={"layer": L["text"]})
    if spec.get("xlines") and version != "R12":
        msp.add_xline(P(0, 0) + (0,), (1, 0, 0), dxfattribs={"layer": L["grid"]})
        msp.add_ray(P(0, 0) + (0,), (0, 1, 0), dxfattribs={"layer": L["grid"]})
    if spec.get("title_far"):
        tb = [P(500.0, 500.0), P(520.0, 500.0), P(520.0, 515.0), P(500.0, 515.0)]
        _rect(msp, tb, L["title"], version)
    if spec.get("paperspace") and version != "R12":
        doc.layout("Layout1").add_line((0, 0), (420, 297), dxfattribs={"layer": L["col"]})

    if spec.get("nest"):
        msp.add_blockref("PLAN", (0, 0), dxfattribs={"layer": "0"})
    doc.saveas(path)
    return str(path)


def _adjacent_cells(a, b) -> List[Tuple[int, int]]:
    (i1, j1), (i2, j2) = a, b
    if j1 == j2:          # horizontal edge at y = j1 between x = i1 .. i1 + 1
        return [(i1, j1), (i1, j1 - 1)]
    return [(i1, j1), (i1 - 1, j1)]


def _rect(target, pts, layer, version):
    if version == "R12":
        target.add_polyline2d(pts, close=True, dxfattribs={"layer": layer})
    else:
        target.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def _cases() -> Dict[str, Dict]:
    c: Dict[str, Dict] = {}
    for shape in ("rect", "L", "T", "U", "courtyard", "cross", "irregular"):
        c[f"shape-{shape}"] = dict(shape=shape, nx=4, ny=4, bays=[3.5, 4.0, 4.5, 5.0])
    for u in UNITS:
        c[f"units-{u}"] = dict(units=u, nx=3, ny=2, bays=[4.0, 5.0])
    for v in ("R12", "R2000", "R2010", "R2018"):
        c[f"version-{v}"] = dict(version=v, nx=3, ny=2)
    for col in ("polyline", "block", "block_scaled", "block_mirrored", "block_nested", "circle", "mixed"):
        c[f"columns-{col}"] = dict(columns=col, nx=3, ny=3)
    for b in ("lwpoly", "to_face", "missing_some", "none", "zero_length_extra"):
        c[f"beams-{b}"] = dict(beams=b, nx=3, ny=3)
    for lay in ("indian", "zero", "random"):
        c[f"layers-{lay}"] = dict(layers=lay, nx=3, ny=2, seed=3)
    for r in (90.0, 180.0, 270.0):
        c[f"rotate-{int(r)}"] = dict(rotate=r, nx=3, ny=2, bays=[4.0, 5.0])
    c["rotate-30-skewed"] = dict(rotate=30.0, nx=3, ny=2)
    c["rotate-0.5-drafting"] = dict(rotate=0.5, nx=3, ny=2)
    c["mirrored"] = dict(mirror=True, nx=3, ny=2)
    c["offset-utm-m"] = dict(units="m", offset=(512345.678, 2034567.891), nx=3, ny=2)
    c["offset-utm-mm"] = dict(units="mm", offset=(512345.678, 2034567.891), nx=3, ny=2)
    c["offset-negative"] = dict(offset=(-150.0, -75.0), nx=3, ny=2)
    c["single-bay"] = dict(nx=1, ny=1, bay=4.0)
    c["single-line"] = dict(nx=5, ny=1, bays=[3.0, 4.0])
    c["long-thin"] = dict(nx=12, ny=1, bay=4.0, bay_y=6.0)
    c["single-column"] = dict(single_column=True, walls="none")
    c["two-columns"] = dict(two_columns=True, walls="none")
    c["three-columns-L"] = dict(three_columns=True, walls="none")
    c["one-row"] = dict(row=True, nx=4, walls="none")
    c["tiny-bays"] = dict(nx=3, ny=3, bay=2.5)
    c["long-spans"] = dict(nx=2, ny=2, bay=10.0)
    c["very-long-spans"] = dict(nx=2, ny=1, bay=12.0)
    c["mixed-bays"] = dict(nx=5, ny=4, bays=[2.7, 3.0, 4.2, 5.5, 7.0], seed=11)
    c["office-6x4"] = dict(nx=6, ny=4, bay=7.5, walls="perimeter")
    c["mall-12x9"] = dict(nx=12, ny=9, bay=8.0, walls="perimeter", noise=False)
    c["column-sizes-varied"] = dict(nx=3, ny=3, col_sizes=[(0.23, 0.23), (0.3, 0.6), (0.6, 0.6), (0.23, 0.45)],
                                    vary_sizes=True)
    c["columns-230"] = dict(nx=3, ny=2, col_sizes=[(0.23, 0.23)])
    c["duplicate-columns"] = dict(duplicate_columns=True, nx=3, ny=2)
    c["walls-only-rect"] = dict(columns="none", beams="none", walls="interior", nx=3, ny=2, bay=4.0)
    c["walls-only-L"] = dict(columns="none", beams="none", walls="interior", shape="L", nx=4, ny=4, bay=4.0)
    c["walls-none"] = dict(walls="none", nx=3, ny=2)
    c["interior-walls"] = dict(walls="interior", nx=3, ny=3)
    c["nested-plan"] = dict(nest=True, nx=3, ny=2)
    c["nested-plan-blocks"] = dict(nest=True, columns="block", nx=3, ny=2)
    c["cantilever-beam"] = dict(cantilever=True, nx=3, ny=2)
    c["xlines-rays"] = dict(xlines=True, nx=3, ny=2)
    c["title-block-far"] = dict(title_far=True, nx=3, ny=2)
    c["paperspace-junk"] = dict(paperspace=True, nx=3, ny=2)
    c["no-noise"] = dict(noise=False, nx=3, ny=2)
    c["L-rotated-90-cm"] = dict(shape="L", rotate=90.0, units="cm", nx=4, ny=4, bay=4.0)
    c["U-blocks-indian-offset"] = dict(shape="U", columns="block", layers="indian", offset=(1000.0, 2000.0),
                                       nx=5, ny=4, bay=4.0)
    c["courtyard-mixed-R12"] = dict(shape="courtyard", columns="polyline", version="R12", nx=3, ny=3, bay=4.5)
    c["irregular-zero-layer-ft"] = dict(shape="irregular", layers="zero", units="ft", nx=4, ny=3, seed=5)
    c["cross-nested-mirrored"] = dict(shape="cross", nest=True, mirror=True, nx=3, ny=3)
    return c


CASES = _cases()


def random_spec(seed: int) -> Dict:
    """A building with every option drawn at random (reproducible from the seed)."""
    r = random.Random(seed)
    return dict(
        seed=seed, shape=r.choice(["rect", "L", "T", "U", "courtyard", "cross", "irregular"]),
        nx=r.randint(1, 7), ny=r.randint(1, 5), bays=r.sample([2.5, 3.0, 3.6, 4.2, 5.0, 6.0, 7.5, 9.0], 3),
        units=r.choice(list(UNITS)), version=r.choice(["R12", "R2000", "R2018"]),
        columns=r.choice(["lwpoly", "polyline", "block", "block_scaled", "block_mirrored", "circle", "mixed"]),
        beams=r.choice(["line", "lwpoly", "to_face", "missing_some", "line"]),
        walls=r.choice(["perimeter", "interior", "none"]), layers=r.choice(["ncs", "indian", "zero", "random"]),
        rotate=r.choice([0.0, 0.0, 90.0, 180.0, 270.0]), mirror=r.random() < 0.2,
        offset=r.choice([(0.0, 0.0), (250.0, -80.0), (500123.0, 2000456.0)]),
        nest=r.random() < 0.2, duplicate_columns=r.random() < 0.15, cantilever=r.random() < 0.2,
        col_sizes=r.choice([[(0.3, 0.45)], [(0.23, 0.23)], [(0.3, 0.3), (0.3, 0.6), (0.45, 0.45)]]),
        vary_sizes=r.random() < 0.4, xlines=r.random() < 0.2, noise=r.random() < 0.8)
