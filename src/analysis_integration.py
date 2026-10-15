"""
Building analysis by independent 2D frames (production path).

The building is sliced into plane frames along every grid line (XZ frames at
constant Y resist X-direction lateral load, YZ frames at constant X resist
Y-direction lateral load).  Each frame is solved with
:class:`src.fea_solver.FrameSolver2D` for the load cases

    DL, LL                 gravity (service), from slab panels, walls, beam self-weight
    EQX / EQY              seismic storey forces (if supplied)
    WLX / WLY              wind storey forces (if supplied)

and the factored combinations of :mod:`src.load_combinations` are applied to
the internal-force diagrams.  Results are written to:

    beam.mu_sagging_knm / mu_hogging_knm / vu_kn / governing_combo   (factored envelopes)
    column.design_forces = [(combo@end, Pu, Mx, My), ...]               (factored)

Limitations (documented in docs/engineering/limitations.md): no torsion /
accidental eccentricity, rigid-diaphragm load sharing by column stiffness,
column axial loads from the tributary takedown (not from the frames) for
gravity cases, beams not on a grid line are not part of any frame.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .fea_solver import FrameSolver2D
from .framing_logic import StructuralMember
from .grid_manager import GridManager
from .load_combinations import IS_456_COMBINATIONS, LoadType
from .logging_config import get_logger

logger = get_logger(__name__)

TOL = 0.1          # m, "lies on plane / line" tolerance
MERGE_TOL = 0.05   # m, node merge tolerance
STATIONS = 11


@dataclass
class LateralLoads:
    """Whole-building storey forces (kN) at floor levels 1..N, bottom to top."""
    eq_x: List[float] = field(default_factory=list)
    eq_y: List[float] = field(default_factory=list)
    wl_x: List[float] = field(default_factory=list)
    wl_y: List[float] = field(default_factory=list)


@dataclass
class AnalysisSummary:
    frames_total: int = 0
    frames_solved: int = 0
    failed_frames: List[str] = field(default_factory=list)
    combinations: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    beams_not_in_frame: List[str] = field(default_factory=list)
    columns_not_in_frame: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed_frames


def build_combinations(has_eq: bool, has_wl: bool) -> List[Tuple[str, Dict[str, float]]]:
    """Expand IS 456 Table 18 / IS 1893 combinations into case factors.
    Wind combinations are generated separately for the X and Y directions."""
    out = []
    for c in IS_456_COMBINATIONS:
        f: Dict[str, float] = {}
        wind = None
        eq = False
        for lt, v in c.factors.items():
            if lt == LoadType.DEAD:
                f["DL"] = v
            elif lt == LoadType.LIVE:
                f["LL"] = v
            elif lt == LoadType.WIND:
                wind = v
            elif lt == LoadType.SEISMIC_X:
                f["EQX"] = v; eq = True
            elif lt == LoadType.SEISMIC_Y:
                f["EQY"] = v; eq = True
        if eq and not has_eq:
            continue
        if wind is not None:
            if not has_wl:
                continue
            for d in ("X", "Y"):
                g = dict(f)
                g["WL" + d] = wind
                out.append((c.name.replace("WL", "WL" + d.lower()), g))
            continue
        out.append((c.name, f))
    return out


# ------------------------------------------------------------- geometry --

def _seg_overlap(p1, p2, a, b, tol=TOL) -> float:
    """Length of overlap between segment p1-p2 and segment a-b when collinear
    (within tol); 0 otherwise."""
    ax, ay = a
    bx, by = b
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return 0.0
    ux, uy = (bx - ax) / L, (by - ay) / L
    for px, py in (p1, p2):
        if abs((px - ax) * uy - (py - ay) * ux) > tol:
            return 0.0
    t1 = (p1[0] - ax) * ux + (p1[1] - ay) * uy
    t2 = (p2[0] - ax) * ux + (p2[1] - ay) * uy
    lo, hi = max(min(t1, t2), 0.0), min(max(t1, t2), L)
    return max(0.0, hi - lo)


def _beam_pts(b: StructuralMember):
    return (b.start_point.x, b.start_point.y), (b.end_point.x, b.end_point.y)


def beam_slab_coefficients(gm: GridManager, beams: List[StructuralMember]) -> Dict[str, float]:
    """Equivalent-UDL width k (m) per beam such that beam UDL = k x area load.

    Two-way panel (ly/lx <= 2): short-edge beams lx/3 (triangle), long-edge
    beams (lx/6)(3 - (lx/ly)^2) (trapezoid) - moment-equivalent UDLs, which
    over-estimate end shear (conservative).  One-way panel: long-edge beams
    lx/2, short-edge beams 0.  Cantilever beams: half the adjacent grid
    spacing on each side x cantilever slab.
    """
    sides_k: Dict[str, Dict[tuple, float]] = {b.id: {} for b in beams}
    for p in gm.slab_panels():
        x0, x1, y0, y1 = p["x0"], p["x1"], p["y0"], p["y1"]
        sx, sy = x1 - x0, y1 - y0
        lx, ly = min(sx, sy), max(sx, sy)
        if p["two_way"]:
            k_short, k_long = lx / 3.0, lx / 6.0 * (3.0 - (lx / ly) ** 2)
        else:
            k_short, k_long = 0.0, lx / 2.0
        horiz_is_short = sx <= sy   # bottom/top edges have length sx
        sides = {
            ("H", round(y0, 3), round(x0, 3), round(x1, 3)): ((x0, y0), (x1, y0), k_short if horiz_is_short else k_long),
            ("H", round(y1, 3), round(x0, 3), round(x1, 3)): ((x0, y1), (x1, y1), k_short if horiz_is_short else k_long),
            ("V", round(x0, 3), round(y0, 3), round(y1, 3)): ((x0, y0), (x0, y1), k_long if horiz_is_short else k_short),
            ("V", round(x1, 3), round(y0, 3), round(y1, 3)): ((x1, y0), (x1, y1), k_long if horiz_is_short else k_short),
        }
        for key, (a, b2, k) in sides.items():
            side_len = math.hypot(b2[0] - a[0], b2[1] - a[1])
            for bm in beams:
                if bm.end_point is None:
                    continue
                p1, p2 = _beam_pts(bm)
                ov = _seg_overlap(p1, p2, a, b2)
                blen = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if ov > 0 and ov >= 0.5 * min(side_len, blen):
                    sides_k[bm.id][key] = sides_k[bm.id].get(key, 0.0) + k
    out = {bid: (max(d.values()) if d else 0.0) for bid, d in sides_k.items()}

    # cantilever beams (one end beyond the grid extents)
    xs, ys = sorted(gm.x_grid_lines), sorted(gm.y_grid_lines)
    if xs and ys:
        for bm in beams:
            if bm.end_point is None:
                continue
            p1, p2 = _beam_pts(bm)
            outside = any(px < xs[0] - TOL or px > xs[-1] + TOL or py < ys[0] - TOL or py > ys[-1] + TOL
                          for px, py in (p1, p2))
            if not outside:
                continue
            if abs(p1[1] - p2[1]) < TOL:      # horizontal cantilever: tributary in Y
                grid, c = ys, p1[1]
            else:
                grid, c = xs, p1[0]
            idx = min(range(len(grid)), key=lambda i: abs(grid[i] - c))
            lo = (grid[idx] - grid[idx - 1]) / 2.0 if idx > 0 else 0.0
            hi = (grid[idx + 1] - grid[idx]) / 2.0 if idx < len(grid) - 1 else 0.0
            out[bm.id] = lo + hi
    return out


def beam_wall_loads(gm: GridManager, beams: List[StructuralMember], messages: List[str]) -> Dict[str, float]:
    """Wall line load (kN/m, one storey of walls) carried by each beam.  Walls
    not lying on a beam are assigned to the nearest parallel beam within 3 m."""
    out = {b.id: 0.0 for b in beams}
    unmatched = 0
    for w in gm.walls:
        a, b2 = (w.start_x, w.start_y), (w.end_x, w.end_y)
        hits = []
        for bm in beams:
            if bm.end_point is None:
                continue
            p1, p2 = _beam_pts(bm)
            if _seg_overlap(p1, p2, a, b2, tol=0.15) > 0 or _seg_overlap(a, b2, p1, p2, tol=0.15) > 0:
                hits.append(bm)
        if not hits:
            wl = math.hypot(b2[0] - a[0], b2[1] - a[1])
            if wl < 1e-6:
                continue
            ux, uy = (b2[0] - a[0]) / wl, (b2[1] - a[1]) / wl
            mx, my = (a[0] + b2[0]) / 2.0, (a[1] + b2[1]) / 2.0
            best, best_d = None, 3.0
            for bm in beams:
                if bm.end_point is None:
                    continue
                p1, p2 = _beam_pts(bm)
                bl = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if bl < 1e-6:
                    continue
                vx, vy = (p2[0] - p1[0]) / bl, (p2[1] - p1[1]) / bl
                if abs(ux * vy - uy * vx) > 0.1:
                    continue
                d = abs((mx - p1[0]) * vy - (my - p1[1]) * vx)
                if d < best_d:
                    best, best_d = bm, d
            if best is None:
                unmatched += 1
                continue
            hits = [best]
        for bm in hits:
            out[bm.id] = max(out[bm.id], w.line_load_kn_m)
    if unmatched:
        messages.append(f"{unmatched} wall segment(s) not near any parallel beam: excluded from beam loads "
                        f"(still included in column takedown)")
    return out


def _level_elevations(gm: GridManager) -> List[float]:
    """Elevation of floor levels 1..N (top of storey 0..N-1)."""
    out = []
    for lvl in range(gm.num_stories):
        tops = [c.z_top for c in gm.columns if c.level == lvl]
        out.append(sum(tops) / len(tops) if tops else (lvl + 1) * gm.story_height_m)
    return out


def _col_dims(col) -> Tuple[float, float]:
    """(dimension along X, dimension along Y) in mm, honouring 90 degree orientation."""
    w, d = col.width_nb, col.depth_nb
    if abs((col.orientation_deg % 180.0) - 90.0) < 1.0:
        w, d = d, w
    return w, d


# ----------------------------------------------------------------- main --

def update_structural_analysis(gm: GridManager, beams: List[StructuralMember], fck: float = 25.0,
                               use_cracked_sections: bool = False, fixed_base: bool = True,
                               lateral: Optional[LateralLoads] = None) -> AnalysisSummary:
    """Analyse the building and write factored design envelopes to beams and
    columns.  See module docstring."""
    summary = AnalysisSummary()
    lateral = lateral or LateralLoads()
    has_eq = bool(lateral.eq_x or lateral.eq_y)
    has_wl = bool(lateral.wl_x or lateral.wl_y)
    combos = build_combinations(has_eq, has_wl)
    summary.combinations = [c[0] for c in combos]

    E = 5000.0 * math.sqrt(fck) * 1000.0          # kN/m^2 (IS 456 Cl 6.2.3.1)
    col_mod, beam_mod = (0.70, 0.35) if use_cracked_sections else (1.0, 1.0)
    N = gm.num_stories
    elev = _level_elevations(gm)
    t_slab = gm.slab_thickness_mm / 1000.0

    if gm.dead_load_kn_m2 <= 0 and gm.live_load_kn_m2 <= 0:
        summary.messages.append("No load intensities recorded on the model - residential defaults used "
                                "(DL 6.125, LL 2.0 kN/m2)")
        q = {"fd": 6.125, "fl": 2.0, "rd": 6.125, "rl": 1.5}
    else:
        q = {"fd": gm.dead_load_kn_m2, "fl": gm.live_load_kn_m2, "rd": gm.roof_dead_kn_m2, "rl": gm.roof_live_kn_m2}

    valid_beams = [b for b in beams if b.end_point is not None
                   and math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y) > 1e-3]
    k_slab = beam_slab_coefficients(gm, valid_beams)
    wall_line = beam_wall_loads(gm, valid_beams, summary.messages)

    def beam_case_loads(bm: StructuralMember, level: int) -> Tuple[float, float]:
        roof = level == N
        sw = bm.properties.width_mm / 1000.0 * max(bm.properties.depth_mm / 1000.0 - t_slab, 0.0) * 25.0
        wall = wall_line.get(bm.id, 0.0) * (0.33 if roof else 1.0)
        dl = k_slab.get(bm.id, 0.0) * (q["rd"] if roof else q["fd"]) + wall + sw
        ll = k_slab.get(bm.id, 0.0) * (q["rl"] if roof else q["fl"])
        return dl, ll

    # reset outputs (analysis may be repeated during design iterations)
    for bm in beams:
        bm.mu_sagging_knm = bm.mu_hogging_knm = bm.vu_kn = 0.0
        bm.design_moment_knm = bm.design_shear_kn = bm.service_udl_kn_m = 0.0
        bm.governing_combo = ""
        bm.analysis_status = "PENDING"
    for col in gm.columns:
        col.design_forces = []

    beam_in_frame = set()
    col_results: Dict[str, Dict[str, Dict[str, Tuple[float, float, float]]]] = {}

    planes = [("XZ", y) for y in sorted(gm.y_grid_lines)] + [("YZ", x) for x in sorted(gm.x_grid_lines)]
    # frame stiffness per level for lateral load sharing
    frame_defs = []
    for plane, cc in planes:
        cols = [c for c in gm.columns if abs((c.y if plane == "XZ" else c.x) - cc) < TOL]
        fbeams = []
        for bm in valid_beams:
            p1, p2 = _beam_pts(bm)
            if plane == "XZ" and abs(p1[1] - cc) < TOL and abs(p2[1] - cc) < TOL and abs(p2[0] - p1[0]) > 1e-3:
                fbeams.append(bm)
            elif plane == "YZ" and abs(p1[0] - cc) < TOL and abs(p2[0] - cc) < TOL and abs(p2[1] - p1[1]) > 1e-3:
                fbeams.append(bm)
        if not cols and not fbeams:
            continue
        kl = [0.0] * N
        for c in cols:
            wx, dy = _col_dims(c)
            I = (dy * wx ** 3 if plane == "XZ" else wx * dy ** 3) / 12.0 / 1e12 * col_mod
            h = max(c.z_top - c.z_bottom, 0.1)
            if 0 <= c.level < N:
                kl[c.level] += 12.0 * E * I / h ** 3
        frame_defs.append((plane, cc, cols, fbeams, kl))
    k_tot = {"XZ": [0.0] * N, "YZ": [0.0] * N}
    for plane, _, _, _, kl in frame_defs:
        for i in range(N):
            k_tot[plane][i] += kl[i]

    for plane, cc, cols, fbeams, kl in frame_defs:
        summary.frames_total += 1
        name = f"{plane}@{cc:.2f}"
        solver = FrameSolver2D(fixed_base=fixed_base, base_level=min([c.z_bottom for c in cols], default=0.0))
        registry: List[Tuple[float, float, int]] = []

        def node(u, z):
            for (nu, nz, idx) in registry:
                if abs(nu - u) < MERGE_TOL and abs(nz - z) < MERGE_TOL:
                    return idx
            idx = solver.add_node(u, z)
            registry.append((u, z, idx))
            return idx

        col_elem = {}
        for c in cols:
            u = c.x if plane == "XZ" else c.y
            wx, dy = _col_dims(c)
            I = (dy * wx ** 3 if plane == "XZ" else wx * dy ** 3) / 12.0 / 1e12 * col_mod
            A = wx * dy / 1e6
            col_elem[c.id] = solver.add_element(node(u, c.z_bottom), node(u, c.z_top), E, I, A)
        beam_elem = {}
        for bm in fbeams:
            p1, p2 = _beam_pts(bm)
            u1, u2 = (p1[0], p2[0]) if plane == "XZ" else (p1[1], p2[1])
            I = bm.properties.width_mm * bm.properties.depth_mm ** 3 / 12.0 / 1e12 * beam_mod
            A = bm.properties.width_mm * bm.properties.depth_mm / 1e6
            for lvl in range(1, N + 1):
                n1, n2 = node(u1, elev[lvl - 1]), node(u2, elev[lvl - 1])
                if n1 == n2:
                    continue
                beam_elem[(bm.id, lvl)] = solver.add_element(n1, n2, E, I, A)

        cases: Dict[str, Tuple[Dict[int, float], Dict[int, List[float]]]] = {
            "DL": ({}, {}), "LL": ({}, {})}
        for (bid, lvl), e in beam_elem.items():
            bm = next(b for b in fbeams if b.id == bid)
            dl, ll = beam_case_loads(bm, lvl)
            cases["DL"][0][e] = dl
            cases["LL"][0][e] = ll
        lat_map = {"XZ": (("EQX", lateral.eq_x), ("WLX", lateral.wl_x)),
                   "YZ": (("EQY", lateral.eq_y), ("WLY", lateral.wl_y))}[plane]
        for cname, forces in lat_map:
            if not forces:
                continue
            nloads: Dict[int, List[float]] = {}
            for lvl in range(1, min(N, len(forces)) + 1):
                tot = k_tot[plane][lvl - 1]
                if tot <= 0 or kl[lvl - 1] <= 0:
                    continue
                share = kl[lvl - 1] / tot * forces[lvl - 1]
                at_level = [(u, idx) for (u, z, idx) in registry if abs(z - elev[lvl - 1]) < MERGE_TOL]
                if not at_level:
                    continue
                n = min(at_level)[1]
                cur = nloads.get(n, [0.0, 0.0, 0.0])
                nloads[n] = [cur[0] + share, cur[1], cur[2]]
            cases[cname] = ({}, nloads)

        res = solver.solve_cases(cases) if solver.elements else {}
        if not res:
            summary.failed_frames.append(f"{name}: {solver.status} {solver.status_message}")
            for bm in fbeams:
                beam_in_frame.add(bm.id)
                _fallback_beam(bm, beam_case_loads, N, combos, f"FALLBACK_{solver.status}")
            continue
        summary.frames_solved += 1

        # beams
        for bm in fbeams:
            beam_in_frame.add(bm.id)
        for (bid, lvl), e in beam_elem.items():
            bm = next(b for b in fbeams if b.id == bid)
            L, _, _ = solver._geom(e)
            xs = [L * k / (STATIONS - 1) for k in range(STATIONS)]
            mc, v1c, v2c = {}, {}, {}
            for cname, r in res.items():
                f = r["forces"][e]
                w = r["udls"].get(e, 0.0)
                mc[cname] = [solver.moment_at(e, x, f, w) for x in xs]
                v1c[cname], v2c[cname] = f[1], f[4]
            for combo, fac in combos:
                m = [sum(fac.get(cn, 0.0) * mc[cn][k] for cn in mc) for k in range(STATIONS)]
                v = max(abs(sum(fac.get(cn, 0.0) * v1c[cn] for cn in mc)), abs(sum(fac.get(cn, 0.0) * v2c[cn] for cn in mc)))
                sag, hog = max(0.0, max(m)), max(0.0, -min(m))
                if sag > bm.mu_sagging_knm:
                    bm.mu_sagging_knm = sag
                if hog > bm.mu_hogging_knm:
                    bm.mu_hogging_knm = hog
                if v > bm.vu_kn:
                    bm.vu_kn = v
                if max(sag, hog) >= bm.design_moment_knm:
                    bm.design_moment_knm = max(sag, hog)
                    bm.governing_combo = combo
            dl, ll = cases["DL"][0][e], cases["LL"][0][e]
            bm.service_udl_kn_m = max(bm.service_udl_kn_m, dl + ll)
            bm.design_shear_kn = bm.vu_kn
            bm.analysis_status = "FEA_SOLVED"

        # columns
        for c in cols:
            e = col_elem[c.id]
            L, _, _ = solver._geom(e)
            entry = {}
            for cname, r in res.items():
                f = r["forces"][e]
                entry[cname] = (solver.moment_at(e, 0.0, f, 0.0), solver.moment_at(e, L, f, 0.0), float(f[0]))
            col_results.setdefault(c.id, {})[plane] = entry

    # beams outside every frame -> simply supported fallback
    for bm in valid_beams:
        if bm.id not in beam_in_frame:
            summary.beams_not_in_frame.append(bm.id)
            _fallback_beam(bm, beam_case_loads, N, combos, "FALLBACK_NOT_IN_FRAME")

    # column combinations (gravity axial from takedown, lateral axial from frames)
    for col in gm.columns:
        planes_res = col_results.get(col.id, {})
        if not planes_res:
            summary.columns_not_in_frame.append(col.id)
        xz, yz = planes_res.get("XZ", {}), planes_res.get("YZ", {})
        forces = []
        for combo, fac in combos:
            pu = fac.get("DL", 0.0) * col.load_dl_kn + fac.get("LL", 0.0) * col.load_ll_kn
            for cn, fv in fac.items():
                if cn in ("EQX", "WLX") and cn in xz:
                    pu += fv * xz[cn][2]
                elif cn in ("EQY", "WLY") and cn in yz:
                    pu += fv * yz[cn][2]
            for end, k in (("bottom", 0), ("top", 1)):
                mx = sum(fv * xz[cn][k] for cn, fv in fac.items() if cn in xz)
                my = sum(fv * yz[cn][k] for cn, fv in fac.items() if cn in yz)
                forces.append((f"{combo}@{end}", pu, mx, my))
        col.design_forces = forces

    if summary.failed_frames:
        summary.messages.append(f"{len(summary.failed_frames)} frame(s) could not be solved; their beams use "
                                f"simply supported fallback moments")
    if summary.beams_not_in_frame:
        summary.messages.append(f"{len(summary.beams_not_in_frame)} beam(s) not on a frame line: simply supported fallback")
    if summary.columns_not_in_frame:
        summary.messages.append(f"{len(summary.columns_not_in_frame)} column(s) not on a frame line: gravity axial + "
                                f"minimum eccentricity only")
    logger.info("Frame analysis: %d/%d frames solved, %d combinations", summary.frames_solved,
                summary.frames_total, len(combos))
    return summary


def _fallback_beam(bm: StructuralMember, loads_fn, N: int, combos, status: str):
    """Simply supported factored moments (wL^2/8 applied to BOTH faces) using
    the worst storey and the worst gravity combination."""
    L = math.hypot(bm.end_point.x - bm.start_point.x, bm.end_point.y - bm.start_point.y)
    worst_w, worst_combo, svc = 0.0, "", 0.0
    for lvl in range(1, N + 1):
        dl, ll = loads_fn(bm, lvl)
        svc = max(svc, dl + ll)
        for combo, fac in combos:
            w = fac.get("DL", 0.0) * dl + fac.get("LL", 0.0) * ll
            if w > worst_w:
                worst_w, worst_combo = w, combo
    m = worst_w * L * L / 8.0
    bm.mu_sagging_knm = bm.mu_hogging_knm = bm.design_moment_knm = m
    bm.vu_kn = bm.design_shear_kn = worst_w * L / 2.0
    bm.governing_combo = worst_combo
    bm.service_udl_kn_m = svc
    bm.analysis_status = status
