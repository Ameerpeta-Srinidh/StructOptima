"""
What each layer of a DXF drawing holds, suggested from the layer name AND from what is drawn on it.

Engineers name layers their own way ("S-COLS", "COLUMN", "Layer 7", "STAMBH", everything on "0"), so the name alone
cannot be trusted. For every layer this module measures what is drawn:

- closed outlines (polylines, circles) of column size (150 mm to 1.5 m);
- line segments that run from one column to another along the column centres (beams);
- line segments through column centres that run past the columns (grid / centre lines);
- line segments with a parallel partner 75-500 mm away (the two faces of a wall);
- text.

The suggested role is one of ROLES. The engineer confirms or corrects it on the Setup page; a confirmed mapping is
used by ``CADParser`` exactly as given. Nothing here decides structural sizes: it only says which entities are
columns, beams and walls.
"""
from dataclasses import dataclass, field
import math
import re
from typing import Dict, List, Optional, Tuple

ROLES = ("column", "beam", "wall", "mixed", "ignore")
ROLE_LABELS = {"column": "Columns", "beam": "Beams", "wall": "Walls", "mixed": "Decide by shape", "ignore": "Ignore"}

COLUMN_SIZE_MM = (150.0, 1500.0)
WALL_GAP_MM = (75.0, 500.0)
SNAP_MM = 150.0               # beam end within half the column + 150 mm of its centre (same rule as the loader)
SEGMENT_CAP = 800             # wall-pair search is quadratic; larger layers are sampled

COLUMN_NAMES = {"COL", "COLS", "COLM", "COLMN", "CLMN", "COLUMN", "COLUMNS", "PILLAR", "PILLARS", "STANCHION",
                "STANCHIONS", "POST", "POSTS"}
BEAM_NAMES = {"BEAM", "BEAMS", "BM", "BMS", "GIRDER", "GIRDERS", "JOIST", "JOISTS"}
NON_FRAME_BEAM_NAMES = {"PLINTH", "LINTEL", "LINTELS", "PB", "LB", "SUNSHADE", "CHAJJA", "CHHAJJA"}
WALL_NAMES = {"WALL", "WALLS", "MASONRY", "BRICK", "BRICKWORK", "BLOCKWORK", "PARTITION", "PARTITIONS"}
IGNORE_NAMES = {
    # annotation
    "IDEN", "TEXT", "TXT", "TAG", "TAGS", "DIM", "DIMS", "DIMENSION", "DIMENSIONS", "ANNO", "NOTE", "NOTES", "LABEL",
    "LABELS", "HATCH", "PATT", "SYMB", "MARK", "MARKS", "NUM", "SCHED", "TITLE", "BORDER", "SHEET", "REV", "REVISION",
    "CLOUD", "NPLT", "DEFPOINTS", "VPORT", "VIEWPORT", "LEVEL", "SECTION", "ELEV",
    # reference lines
    "GRID", "GRIDS", "AXIS", "AXES", "CENTRE", "CENTER", "CL",
    # architecture and services that carry no frame member
    "DOOR", "DOORS", "DR", "WINDOW", "WINDOWS", "WIN", "WDW", "GLAZ", "GLAZING", "FURN", "FURNITURE", "FIXT", "EQPM",
    "PLUMB", "PLUMBING", "SANITARY", "ELEC", "ELECTRICAL", "LIGHT", "LIGHTING", "STAIR", "STAIRS", "LANDSCAPE",
    "TREE", "TREES", "AREA", "ROOM", "ROOMS", "NAME", "NAMES"}


def name_tokens(name: str) -> List[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", (name or "").upper()) if t]


@dataclass
class LayerInfo:
    name: str
    n_entities: int = 0
    n_outlines: int = 0                 # closed polylines
    n_column_outlines: int = 0          # closed outlines / circles of column size
    typical_outline_mm: Optional[Tuple[int, int]] = None
    n_circles: int = 0
    n_column_circles: int = 0           # circles of column size (columns on column layers, symbols elsewhere)
    n_framed_circles: int = 0           # of those, circles where two or more lines end (columns, D-36)
    n_segments: int = 0                 # line segments (lines, open polylines, edges of large closed outlines)
    n_beam_like: int = 0                # run from column to column along the centres
    n_axis_like: int = 0                # through column centres and past them (grid lines)
    n_wall_pairs: int = 0               # with a parallel partner a wall thickness away
    typical_gap_mm: Optional[int] = None
    n_texts: int = 0
    text_samples: List[str] = field(default_factory=list)
    role: str = "ignore"
    confidence: str = "low"             # "high" (name and drawing agree), "medium" (drawing only), "low"
    reason: str = ""

    def contents(self) -> str:
        parts = []
        rects = self.n_column_outlines - self.n_column_circles
        if rects:
            sz = f" of about {self.typical_outline_mm[0]} x {self.typical_outline_mm[1]} mm" if self.typical_outline_mm else ""
            parts.append(f"{rects} column-sized outline(s){sz}")
        if self.n_column_circles:
            parts.append(f"{self.n_column_circles} circle(s) of column size")
        if self.n_outlines - self.n_column_outlines > 0:
            parts.append(f"{self.n_outlines - self.n_column_outlines} other closed outline(s)")
        if self.n_segments:
            parts.append(f"{self.n_segments} line segment(s)")
        if self.n_texts:
            parts.append(f"{self.n_texts} text(s)")
        return ", ".join(parts) or f"{self.n_entities} other entit{'y' if self.n_entities == 1 else 'ies'}"


# units tried for a drawing without a plausible $INSUNITS, in order of preference (Indian practice)
UNIT_CANDIDATES = [("millimetres", 0.001), ("metres", 1.0), ("centimetres", 0.01), ("inches", 0.0254), ("feet", 0.3048)]


def drawing_unit_m(parser) -> float:
    """Metres per drawing unit: the declared $INSUNITS when it gives a plausible building (1-1000 m); otherwise the
    unit (UNIT_CANDIDATES) under which the drawing looks like a building - extent 2-1000 m, typical column spacing
    1.5-15 m (grid bubbles near the end columns pull the median down), most closed outlines / circles 150 mm -
    1.5 m (column-sized) - preferring the earlier unit on a tie; without such evidence the old rule (millimetres
    when coordinates exceed 500). The reason is kept in
    ``parser.unit_reason`` (D-35: R12 files have no $INSUNITS, and survey coordinates broke the size rule)."""
    cached = getattr(parser, "_unit_cache", None)
    if cached is not None:
        return cached
    xs, ys, outlines = [], [], []
    for e in parser._flat():
        t = e.dxftype()
        if t == "LINE":
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts = _points(parser, e)
            for x, y in pts:
                xs.append(x)
                ys.append(y)
            outline = parser._outline(e)                # the same closed-outline test as the layer analysis
            if outline is not None and len(outline) >= 3:
                w, d, _, cx, cy = parser._rect_dims(outline)
                outlines.append((min(w, d), max(w, d), cx, cy))
        elif t == "CIRCLE":
            r = e.dxf.radius
            outlines.append((2 * r, 2 * r, e.dxf.center.x, e.dxf.center.y))
    declared = parser.get_unit_scale()
    if not xs:
        parser._unit_cache, parser.unit_reason = declared or 0.001, "declared" if declared else "default"
        return parser._unit_cache
    extent = max(max(xs) - min(xs), max(ys) - min(ys))
    if declared and 1.0 <= extent * declared <= 1000.0:
        parser._unit_cache, parser.unit_reason = declared, "declared"
        return declared

    def score(u):
        sized = [(cx, cy, a) for a, b, cx, cy in outlines if 0.15 <= a * u and b * u <= 1.5]
        spacing_ok = False
        near = []
        for i, (x, y, a) in enumerate(sized):          # nearest DISTINCT column (an outline drawn twice is one)
            d = [math.hypot(x - x2, y - y2) for j, (x2, y2, _) in enumerate(sized) if j != i]
            d = [v for v in d if v > 0.5 * a]
            if d:
                near.append(min(d))
        if near:
            near.sort()
            spacing_ok = 1.5 <= near[len(near) // 2] * u <= 15.0
        return (2.0 <= extent * u <= 1000.0, spacing_ok, len(sized))

    scored = [(score(u), -k, name, u) for k, (name, u) in enumerate(UNIT_CANDIDATES)]
    best = max(scored)
    if best[0][0] and best[0][1]:
        parser._unit_cache, parser.unit_reason = best[3], (
            f"{best[2]} (no usable $INSUNITS: then {best[0][2]} outlines are column-sized, about 1.5-15 m apart, in a "
            f"building {extent * best[3]:.0f} m across)")
        return best[3]
    u = 0.001 if max(max(map(abs, xs)), max(map(abs, ys))) > 500 else 1.0
    parser._unit_cache, parser.unit_reason = u, (f"{'millimetres' if u == 0.001 else 'metres'} (no usable "
                                                 f"$INSUNITS and no column outlines to judge from: coordinate size)")
    return u


def _points(parser, e) -> List[Tuple[float, float]]:
    if e.dxftype() == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y in parser._lwpoly_xy(e)]
    return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]


def _closed(e) -> bool:
    return bool(getattr(e, "closed", False)) if e.dxftype() == "LWPOLYLINE" else bool(getattr(e, "is_closed", False))


def entity_text(e) -> Optional[str]:
    t = e.dxftype()
    if t == "TEXT":
        return (e.dxf.text or "").strip()
    if t == "MTEXT":
        try:
            return e.plain_text().strip()
        except Exception:  # malformed MTEXT formatting codes: raw text is good enough for a sample
            return (e.text or "").strip()
    return None


class _Geometry:
    """Column outlines and line segments of every layer, in drawing units."""

    def __init__(self, parser):
        self.parser = parser
        self.unit_m = drawing_unit_m(parser)
        self.by_layer: Dict[str, dict] = {}
        for e in parser._flat():
            layer = e.dxf.get("layer", "0")
            d = self.by_layer.setdefault(layer, {"n": 0, "outlines": [], "circles": [], "segs": [], "texts": []})
            d["n"] += 1
            t = e.dxftype()
            if t == "LINE":
                d["segs"].append(((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)))
            elif t in ("LWPOLYLINE", "POLYLINE"):
                pts = parser._outline(e)
                if pts is not None:
                    w, dp, ang, cx, cy = parser._rect_dims(pts)
                    d["outlines"].append({"x": cx, "y": cy, "w": w, "d": dp, "pts": pts})
                else:
                    p = _points(parser, e)
                    d["segs"] += list(zip(p, p[1:])) + ([(p[-1], p[0])] if _closed(e) and len(p) > 2 else [])
            elif t == "CIRCLE":
                d["circles"].append({"x": e.dxf.center.x, "y": e.dxf.center.y, "w": 2 * e.dxf.radius,
                                     "d": 2 * e.dxf.radius})
            else:
                txt = entity_text(e)
                if txt:
                    d["texts"].append(txt)

    def mm(self, v: float) -> float:
        return v * self.unit_m * 1000.0

    def framed_circles(self, circles) -> list:
        """Column-sized circles at which two or more line ends (of any layer) lie, within the beam-end snap (half
        the circle + SNAP_MM): circular columns with beams / walls framing in. A grid bubble has one grid line
        ending at it and is left out (D-36: circular columns drawn on layer 0 or an unnamed layer were dropped)."""
        if not circles:
            return []
        if not hasattr(self, "_ends"):
            self._ends = [p for d in self.by_layer.values() for s in d["segs"] for p in s]
        snap = SNAP_MM / (self.unit_m * 1000.0)
        out = []
        for c in circles:
            if not self.column_sized(c):
                continue
            r = 0.5 * c["w"] + snap
            if sum(1 for (x, y) in self._ends if math.hypot(x - c["x"], y - c["y"]) <= r) >= 2:
                out.append(c)
        return out

    def column_sized(self, o) -> bool:
        lo, hi = COLUMN_SIZE_MM
        return lo <= self.mm(min(o["w"], o["d"])) and self.mm(max(o["w"], o["d"])) <= hi

    def classify_segment(self, seg, centres) -> str:
        """'beam' (column to column on the centres), 'axis' (through column centres, past the end columns) or
        'other'. ``centres``: (x, y, half size) in drawing units."""
        (x1, y1), (x2, y2) = seg
        ln = math.hypot(x2 - x1, y2 - y1)
        if ln <= 0 or not centres:
            return "other"
        ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
        snap = SNAP_MM / (self.unit_m * 1000.0)

        def near(px, py):
            best = min(centres, key=lambda c: math.hypot(px - c[0], py - c[1]))
            return best if math.hypot(px - best[0], py - best[1]) <= best[2] + snap else None

        def on_line(c):                      # centre lies on the segment's line, within a quarter of the column
            return abs((c[0] - x1) * -uy + (c[1] - y1) * ux) <= max(0.25 * c[3], 50.0 / (self.unit_m * 1000.0))

        a, b = near(x1, y1), near(x2, y2)
        if a is not None and b is not None and a is not b and on_line(a) and on_line(b):
            return "beam"
        through = [c for c in centres if on_line(c) and -c[2] <= (c[0] - x1) * ux + (c[1] - y1) * uy <= ln + c[2]]
        if through and (a is None or b is None):
            return "axis"
        return "other"

    def wall_pairs(self, segs) -> Tuple[int, Optional[int]]:
        """Number of segments with a parallel partner 75-500 mm away (overlapping >= 100 mm); most frequent gap."""
        paired, gap = self.paired_segments(segs)
        return len(paired), gap

    def paired_segments(self, segs, min_overlap_mm: float = 100.0):
        """(indices of segments with a parallel partner a wall thickness away, most frequent gap in mm)."""
        lo, hi = (v / (self.unit_m * 1000.0) for v in WALL_GAP_MM)
        min_overlap = min_overlap_mm / (self.unit_m * 1000.0)
        s = []
        idx = []
        for k, ((x1, y1), (x2, y2)) in enumerate(segs[:SEGMENT_CAP]):
            ln = math.hypot(x2 - x1, y2 - y1)
            if ln >= min_overlap:
                s.append((x1, y1, (x2 - x1) / ln, (y2 - y1) / ln, ln))
                idx.append(k)
        paired, gaps = set(), []
        for i, (ax, ay, ux, uy, ln) in enumerate(s):
            for j in range(i + 1, len(s)):
                bx, by, vx, vy, ln2 = s[j]
                if abs(ux * vy - uy * vx) > math.sin(math.radians(2)):
                    continue
                gap = abs((bx - ax) * -uy + (by - ay) * ux)
                if not lo <= gap <= hi:
                    continue
                t1 = (bx - ax) * ux + (by - ay) * uy
                t2 = t1 + ln2 * (vx * ux + vy * uy)
                if min(max(t1, t2), ln) - max(min(t1, t2), 0.0) < min_overlap:
                    continue
                paired.update((idx[i], idx[j]))
                gaps.append(round(self.mm(gap) / 5.0) * 5)
        return paired, (max(set(gaps), key=gaps.count) if gaps else None)


def _name_role(tokens: List[str]) -> Optional[Tuple[str, str]]:
    ts = set(tokens)
    if ts & IGNORE_NAMES:
        return "ignore", f"the name says {'/'.join(sorted(ts & IGNORE_NAMES)).lower()}"
    if ts & NON_FRAME_BEAM_NAMES:
        return "ignore", ("the name says plinth / lintel beam: these are not floor beams of the frame (StructOptima "
                          "designs the floor beams on the column grid). Choose Beams if they are floor beams")
    if ts & COLUMN_NAMES:
        return "column", "the name says columns"
    if ts & BEAM_NAMES:
        return "beam", "the name says beams"
    if ts & WALL_NAMES or any("WALL" in t for t in tokens):
        return "wall", "the name says walls"
    return None


def analyse_layers(parser) -> List[LayerInfo]:
    """One LayerInfo per layer that holds entities, with the suggested role, a confidence and the reason."""
    if parser.doc is None:
        parser.load()
    g = _Geometry(parser)
    infos: Dict[str, LayerInfo] = {}
    names: Dict[str, Optional[Tuple[str, str]]] = {}
    for layer, d in g.by_layer.items():
        cols = [o for o in d["outlines"] if g.column_sized(o)]
        circ = [c for c in d["circles"] if g.column_sized(c)]
        info = LayerInfo(name=layer, n_entities=d["n"], n_outlines=len(d["outlines"]), n_circles=len(d["circles"]),
                         n_column_outlines=len(cols) + len(circ), n_column_circles=len(circ),
                         n_framed_circles=len(g.framed_circles(circ)), n_texts=len(d["texts"]))
        sized = cols or circ
        if sized:
            ws = sorted(round(g.mm(o["w"]) / 5) * 5 for o in sized)
            ds = sorted(round(g.mm(o["d"]) / 5) * 5 for o in sized)
            info.typical_outline_mm = (int(ws[len(ws) // 2]), int(ds[len(ds) // 2]))
        seen = []
        for t in d["texts"]:
            if t not in seen:
                seen.append(t)
        info.text_samples = seen[:8]
        # edges of closed outlines that are not columns (rooms, slabs, walls drawn as closed shapes) are lines too
        for o in d["outlines"]:
            if not g.column_sized(o):
                p = o["pts"]
                d["segs"] += list(zip(p, p[1:] + p[:1]))
        info.n_segments = len(d["segs"])
        infos[layer] = info
        names[layer] = _name_role(name_tokens(layer))

    # column centres for the beam / grid-line tests: layers named as columns, or holding several column outlines
    def column_candidates(layer):
        nm, d = names[layer], g.by_layer[layer]
        if nm and nm[0] in ("ignore", "beam", "wall"):
            return []
        rects = [o for o in d["outlines"] if g.column_sized(o)]
        circles = [c for c in d["circles"] if g.column_sized(c)]
        if nm and nm[0] == "column":
            return rects + circles
        framed = g.framed_circles(circles)           # unnamed layers: lone circles are usually symbols (bubbles)
        return rects + framed if len(rects) + len(framed) >= 2 else []

    centres = []
    for layer in g.by_layer:
        for o in column_candidates(layer):
            half = 0.5 * max(o["w"], o["d"])
            centres.append((o["x"], o["y"], half, min(o["w"], o["d"])))

    for layer, info in infos.items():
        d = g.by_layer[layer]
        kinds = [g.classify_segment(s, centres) for s in d["segs"]]
        info.n_beam_like = kinds.count("beam")
        info.n_axis_like = kinds.count("axis")
        info.n_wall_pairs, info.typical_gap_mm = g.wall_pairs([s for s, k in zip(d["segs"], kinds) if k == "other"])
        _suggest(info, names[layer])

    # no wall and no column layer at all: lines that were left over are the architecture (previous behaviour)
    vals = list(infos.values())
    if not any(i.role in ("wall", "column", "mixed") for i in vals):
        for i in vals:
            if i.role == "ignore" and i.confidence == "low" and i.n_segments:
                i.role, i.confidence = "wall", "low"
                i.reason = "no wall or column layer was found, so the lines on this layer are taken as walls"
    return sorted(vals, key=lambda i: (ROLES.index(i.role), i.name))


def _suggest(info: LayerInfo, name: Optional[Tuple[str, str]]) -> None:
    n_lines = info.n_segments
    if name is not None:
        role, why = name
        info.role = role
        if role == "column":
            if info.n_column_outlines:
                info.confidence = "high"
                info.reason = f"{why} and it holds {info.contents()}"
            elif info.n_outlines:
                info.confidence = "low"
                info.reason = (f"{why}, but its closed outlines are not 150 mm - 1.5 m: check the drawing units")
            else:
                info.confidence = "low"
                info.reason = (f"{why}, but nothing closed is drawn on it: columns must be closed outlines or "
                               f"circles to be read")
        elif role == "beam":
            info.confidence = "high" if n_lines else "low"
            info.reason = why if n_lines else f"{why}, but it holds no lines"
        elif role == "wall":
            info.confidence = "high" if n_lines else "low"
            gap = f", faces about {info.typical_gap_mm} mm apart" if info.typical_gap_mm else ""
            info.reason = f"{why}{gap}" if n_lines else f"{why}, but it holds no lines"
        else:
            info.confidence = "high"
            info.reason = why
        return
    # column-shaped: rectangles, and circles with two or more lines ending at them (lone circles are symbols)
    rects = info.n_column_outlines - info.n_column_circles + info.n_framed_circles
    geometric = info.n_outlines + info.n_circles + max(0, n_lines - info.n_axis_like)
    if rects >= 2 and info.n_beam_like + info.n_wall_pairs == 0:
        info.role, info.confidence = "column", "medium"
        info.reason = f"shaped like columns: {info.contents()}"
    elif rects >= 2:
        info.role, info.confidence = "mixed", "medium"
        info.reason = (f"holds column-sized outlines and lines together ({info.contents()}): outlines are read as "
                       f"columns, lines from column to column as beams, line pairs as walls")
    elif n_lines and info.n_beam_like >= max(2, 0.6 * (n_lines - info.n_axis_like)):
        info.role, info.confidence = "beam", "medium"
        info.reason = f"shaped like beams: {info.n_beam_like} of {n_lines} lines run from column to column"
    elif n_lines and info.n_wall_pairs >= max(2, 0.5 * (n_lines - info.n_axis_like - info.n_beam_like)):
        info.role, info.confidence = "wall", "medium"
        info.reason = f"shaped like walls: lines in parallel pairs about {info.typical_gap_mm} mm apart"
    elif n_lines and info.n_axis_like >= 0.6 * n_lines:
        info.role, info.confidence = "ignore", "medium"
        info.reason = "lines through the column centres running past the building: grid / centre lines"
    elif info.n_texts and not geometric:
        info.role, info.confidence = "ignore", "high"
        info.reason = "text only"
    else:
        info.role, info.confidence = "ignore", "low"
        info.reason = f"not recognised ({info.contents()}): choose a role if it holds structure"


def suggested_roles(parser) -> Dict[str, str]:
    return {i.name: i.role for i in analyse_layers(parser)}
