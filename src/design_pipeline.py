"""
End-to-end design pipeline (production path for app.py and main.py).

    geometry (GridManager + plan beams)
      -> load intensities from the occupancy (building_types)
      -> iterate:  load takedown -> seismic + wind storey forces
                   -> frame analysis (DL, LL, EQ, WL; IS 456/IS 1893 combinations)
                   -> beam + column design (sections grow until they pass)
         until member sizes stop changing
      -> slabs, staircase, footings
      -> quantities, BBS, masonry, audit, joint / SCWB checks, stability, warnings
      -> overall status + list of failures

Everything here is preliminary design support.  See docs/engineering/limitations.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .analysis_integration import (AnalysisSummary, LateralLoads, SeismicSpec, beam_slab_coefficients,
                                   update_structural_analysis, web_self_weight_kn_m)
from .building_types import get_load_parameters
from .foundation_eng import Footing, check_footing_overlaps, design_footing
from .grid_manager import GridManager, check_plan_geometry
from .logging_config import get_logger
from .materials import Concrete

logger = get_logger(__name__)

PREFERRED_COLUMN_SIZES = [230, 300, 350, 380, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000]

# Storey drift limit under the design lateral force with partial safety factor
# 1.0: IS 1893 (Part 1):2016 Cl 7.11.1.1 (0.004 h) - checked against the printed standard 2026-10-20
# against the printed standard (docs/engineering/standards-register.md).
EQ_DRIFT_LIMIT = 0.004
# Lateral sway at the top under transient wind load: IS 456:2000 Cl 20.5 as
# (H/500, "should") - checked 2026-10-20.  Serviceability -> WARN, not FAIL.
WIND_TOP_SWAY_LIMIT = 1.0 / 500.0
# Soft storey (IS 1893 Table 6(i), Amd 2: "less than the storey above"): drops of the computed storey stiffness
# up to 10 % are treated as numerical / load-pattern variation (decision D-27, approved 2026-10-20)
SOFT_STOREY_TOLERANCE = 0.10

# Checks that are NOT performed, whatever the status says (gap analysis N17).
# Shown with every result so PASS cannot be read as complete engineering validation.
CHECKS_NOT_PERFORMED = [
    "Flexible floor diaphragms (re-entrant corners, large openings - IS 1893 Table 5 as amended), diaphragm, collector "
    "and chord design: the 3D dynamic model has rigid floors",
    "Time history analysis, site-specific spectra, soil-structure interaction, P-Delta",
    "Orthogonal seismic combination (100 % + 30 %, IS 1893 6.3.2.2) and vertical seismic action (6.3.3.1, Amd 2)",
    "Imposed loads on corridors, stairs and balconies (IS 875-2 Table 1: 3.0 / 4.0 kN/m2) - one floor load is used",
    "Wind topography factor k3 and cyclonic importance factor k4 (IS 875-3 6.3.3, 6.3.4) - taken as 1.0",
    "Pattern (chequerboard) live loading",
    "P-Delta / second-order analysis; column effective length is taken as 1.0 x storey height",
    "IS 13920 ductile detailing design (confining steel, capacity-design shear, joint reinforcement)",
    "Development length, lap splices and bar curtailment in member design",
    "Beam torsion design and deflection beyond basic span/depth ratios",
    "Footing sizing for base moments, settlement and founding level",
]
VERIFICATION_STATUS = "NOT_VERIFIED"   # no output has been independently verified by an engineer


@dataclass
class DesignInputs:
    num_stories: int = 2
    story_height_m: float = 3.5
    building_type_name: str = "Residential"
    wall_load_kn_m: float = 12.0          # used only when the model has no Wall objects
    sbc_kn_m2: float = 200.0
    conc_grade: str = "M25"
    fy: float = 415.0
    seismic_zone: str = "III"
    soil_type: str = "II"
    structural_system: str = "OMRF"       # OMRF (R=3, default) | SMRF (R=5)
    importance_factor: Optional[float] = None
    wind_zone: Any = None                 # wind_load.WindZone or None to skip wind
    terrain_category: Any = None
    wind_opening_percentage: float = 10.0
    use_cracked_sections: bool = True
    fixed_base: bool = True
    add_staircase: bool = False
    wall_core_thickness_mm: float = 200.0
    mortar_ratio: int = 4
    wall_opening_fraction: float = 0.33
    include_interior_walls: bool = False
    generate_walls_if_missing: bool = True
    align_to_wall: Optional[bool] = None   # None -> residential occupancies
    # D-29: columns in 230 mm wall lines get a 230 mm side across the wall (Zone II OMRF only); None -> residential
    column_matches_wall: Optional[bool] = None
    use_fly_ash: bool = False
    exposure: str = "Moderate"              # IS 456 Table 3 (covers Table 16, grade Table 5)
    nbc_construction_type: int = 2          # NBC 2016 Part 4 Table 1 type of construction (fire ratings)
    max_iterations: int = 6
    le_factor: float = 1.0
    project_name: str = "Project"


@dataclass
class DesignResults:
    gm: GridManager
    beams: list
    all_beams: list
    footings: List[Footing]
    bom: Any
    wall_bom: Any
    audit_results: list
    auditor_math: List[str]
    project_bbs: Any
    seismic_result: Any
    wind_result: Any
    stab_checks: list
    stab_summary: Any
    safety_summary: Any
    building_weight: float
    analysis_summary: AnalysisSummary
    load_params: Any
    iterations: int = 0
    converged: bool = True
    status: str = "PASS"
    failures: List[Dict[str, str]] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    drift_results: List[Dict[str, Any]] = field(default_factory=list)
    checks_not_performed: List[str] = field(default_factory=lambda: list(CHECKS_NOT_PERFORMED))
    verification: str = VERIFICATION_STATUS

    @property
    def status_label(self) -> str:
        """Status text for screens and reports: never a bare PASS."""
        return {"PASS": "PASS (implemented checks only) - NOT VERIFIED",
                "WARN": "WARN - review required - NOT VERIFIED",
                "FAIL": "FAIL"}.get(self.status, self.status)


WALL_COLUMN_MM = 230.0          # brick wall with plaster; column side across the wall (D-29)
WALL_COLUMN_MAX_LONG_MM = 900.0  # IS 456 32.1: longer than 4 x thickness (920 mm) is a wall, not a column
MIN_WALL_FOR_MATCH_MM = 200.0    # full-brick walls (200 mm core, 230 mm finished); half-brick walls do not qualify


def _column_wall_dirs(gm: GridManager, x: float, y: float) -> Dict[str, float]:
    """{"x" / "y": wall length (m)} of full-brick walls whose centre line passes through the column centre."""
    out: Dict[str, float] = {}
    for w in gm.walls:
        if w.thickness_mm < MIN_WALL_FOR_MATCH_MM - 1e-6:
            continue
        dx, dy = w.end_x - w.start_x, w.end_y - w.start_y
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            continue
        ux, uy = dx / ln, dy / ln
        along = (x - w.start_x) * ux + (y - w.start_y) * uy
        off = abs((x - w.start_x) * -uy + (y - w.start_y) * ux)
        if off <= 0.12 and -0.15 <= along <= ln + 0.15:
            d = "x" if abs(dx) >= abs(dy) else "y"
            out[d] = out.get(d, 0.0) + ln
    return out


def apply_wall_width_columns(gm: GridManager, beams, fck: float, fy: float) -> int:
    """D-29: every column stack standing in a full-brick wall line gets its side across the wall equal to
    WALL_COLUMN_MM and the other side from the axial demand (0.4 fck Ac + 0.67 fy Asc >= 1.5 P at 0.8 % steel,
    IS 456 39.3), at least 450 and at most WALL_COLUMN_MAX_LONG_MM. A column on one wall line runs along it;
    where walls meet (corners, T and cross junctions) the long side goes to the direction that has fewer long sides
    so far, so that both directions keep similar column stiffness. Free-standing columns are unchanged. Beams that
    frame into a 230 mm side are made 230 mm wide (if not deeper than 750 mm). Returns the number of stacks set."""
    stacks: Dict[Tuple[float, float], list] = {}
    for c in gm.columns:
        stacks.setdefault((round(c.x, 3), round(c.y, 3)), []).append(c)
    n = 0
    t = WALL_COLUMN_MM
    walls_at = {k: _column_wall_dirs(gm, *k) for k in stacks}
    count = {"x": sum(1 for d in walls_at.values() if set(d) == {"x"}),
             "y": sum(1 for d in walls_at.values() if set(d) == {"y"})}
    choice: Dict[Tuple[float, float], str] = {}
    for key in sorted(walls_at):
        dirs = walls_at[key]
        if len(dirs) == 1:
            choice[key] = next(iter(dirs))
        elif dirs:
            d = min(("x", "y"), key=lambda k: (count[k], -dirs[k], k))
            choice[key] = d
            count[d] += 1
    for (x, y), stack in stacks.items():
        d = choice.get((x, y))
        if d is None:
            continue
        p_kn = max(c.load_kn for c in stack)
        ag = 1.5 * p_kn * 1000.0 / (0.4 * fck * 0.992 + 0.67 * fy * 0.008)
        need = max(450.0, ag / t)
        long_side = next((float(p) for p in PREFERRED_COLUMN_SIZES if p >= need - 1e-6), need)
        if long_side > WALL_COLUMN_MAX_LONG_MM:
            continue
        for c in stack:
            c.wall_dir = d
            c.width_nb, c.depth_nb = (long_side, t) if d == "x" else (t, long_side)
        n += 1
    if n:
        by_xy = {k: v[0] for k, v in stacks.items()}
        for b in beams:
            if b.end_point is None or b.properties.depth_mm > 750.0:
                continue
            horiz = abs(b.end_point.y - b.start_point.y) < 1e-6
            ends = [by_xy.get((round(p.x, 3), round(p.y, 3))) for p in (b.start_point, b.end_point)]
            if any(e is not None and e.wall_dir == ("x" if horiz else "y") for e in ends):
                b.properties.width_mm = min(b.properties.width_mm, t)
    return n


def _grow_stack(stack, design=None) -> bool:
    """Grow a column stack one preferred size. Wall columns grow along the wall (keeping the wall width) up to
    WALL_COLUMN_MAX_LONG_MM; when bending about the thin side governs the interaction (``design``: the column's
    RebarResult), or the long side is at its limit, both sides grow and the column no longer matches the wall.
    False if at the limit."""
    c0 = stack[0]
    w, d = c0.width_nb, c0.depth_nb
    if max(w, d) >= 1500:
        return False
    thin_governs = False
    if c0.wall_dir in ("x", "y") and design is not None and design.mux1_knm > 0 and design.muy1_knm > 0:
        tx, ty = abs(design.mux_design_knm) / design.mux1_knm, abs(design.muy_design_knm) / design.muy1_knm
        thin_governs = (ty if c0.wall_dir == "x" else tx) > (tx if c0.wall_dir == "x" else ty)
    if c0.wall_dir in ("x", "y") and not thin_governs:
        long_side = w if c0.wall_dir == "x" else d
        nl = _next_pref(long_side)
        if nl <= WALL_COLUMN_MAX_LONG_MM:
            for c in stack:
                if c.wall_dir == "x":
                    c.width_nb = nl
                else:
                    c.depth_nb = nl
            return True
    for c in stack:
        c.wall_dir = None
    nw, nd = _next_pref(w), _next_pref(d)
    for c in stack:
        c.width_nb, c.depth_nb = nw, nd
    return True


def beams_wider_than_columns(gm: GridManager, beams) -> List[Tuple[str, float, str, float]]:
    """(beam id, beam width, column id, column side across the beam) where a beam is wider than the column it
    frames into: its outer bars would pass outside the column cage."""
    cols = {(round(c.x, 3), round(c.y, 3)): c for c in gm.columns if c.level == 0}
    out = []
    for b in beams:
        if b.end_point is None:
            continue
        horiz = abs(b.end_point.y - b.start_point.y) < 1e-6
        for p in (b.start_point, b.end_point):
            c = cols.get((round(p.x, 3), round(p.y, 3)))
            if c is None:
                continue
            across = c.depth_nb if horiz else c.width_nb
            if b.properties.width_mm > across + 1.0:
                out.append((b.id, b.properties.width_mm, c.id, across))
                break
    return out


def _next_pref(v: float) -> float:
    for p in PREFERRED_COLUMN_SIZES:
        if p > v + 1e-6:
            return float(p)
    return float(math.ceil((v + 50) / 50.0) * 50.0)


def storey_seismic_weights(gm: GridManager, beams, ll_factor_fn) -> Tuple[List[float], List[float], float]:
    """Lumped seismic weight at floor levels 1..N (kN) and their heights.

    Level j: slab dead load over the slab panels (roof intensity at the top),
    beam webs, half the walls and columns of the storeys below and above
    (parapet = 1/3 storey wall at roof), plus the IS 1893 fraction of floor
    live load (none at roof).  Ground-storey half walls/columns go to the base.
    """
    N = gm.num_stories
    panels = gm.slab_panels()
    area = sum((p["x1"] - p["x0"]) * (p["y1"] - p["y0"]) for p in panels) or gm.width_m * gm.length_m
    t = gm.slab_thickness_mm / 1000.0
    # N13: extra dead load of panels designed thicker than the occupancy slab
    pex = gm.panel_extra_dead_kn_m2()
    extra_w = sum((p["x1"] - p["x0"]) * (p["y1"] - p["y0"]) * pex.get((p["i"], p["j"]), 0.0) for p in panels)
    valid = [b for b in beams if b.end_point is not None]
    over = beam_slab_coefficients(gm, valid, return_extra=True)[2] if valid else {}
    beam_w = sum(web_self_weight_kn_m(b, t, over.get(b.id, 0.0)) *
                 math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y) for b in valid)
    wall_storey = sum(w.length_m * w.line_load_kn_m for w in gm.walls)
    col_storey = {lvl: sum(c.width_nb * c.depth_nb / 1e6 * (c.z_top - c.z_bottom) * 25.0
                           for c in gm.columns if c.level == lvl) for lvl in range(N)}
    weights, heights = [], []
    for j in range(1, N + 1):
        roof = j == N
        w = area * (gm.roof_dead_kn_m2 if roof else gm.dead_load_kn_m2) + extra_w + beam_w
        w += 0.5 * wall_storey + (0.33 * wall_storey if roof else 0.5 * wall_storey)
        w += 0.5 * col_storey.get(j - 1, 0.0) + (0.0 if roof else 0.5 * col_storey.get(j, 0.0))
        if not roof:
            w += area * gm.live_load_kn_m2 * ll_factor_fn(gm.live_load_kn_m2)
        weights.append(w)
        tops = [c.z_top for c in gm.columns if c.level == j - 1]
        heights.append(sum(tops) / len(tops) if tops else j * gm.story_height_m)
    return weights, heights, area


def drift_checks(storey_drift: Dict[str, Dict[int, Tuple[float, float, str]]],
                 top_displacement: Dict[str, Tuple[float, str]], total_height_m: float) -> List[Dict[str, Any]]:
    """Storey drift rows from the unfactored lateral cases.

    EQ cases: every storey against ``EQ_DRIFT_LIMIT`` (FAIL above).  Wind cases:
    storey drifts reported for information and the top sway against
    ``WIND_TOP_SWAY_LIMIT`` x H (WARN above).
    """
    rows: List[Dict[str, Any]] = []
    for case in ("EQX", "EQY", "WLX", "WLY"):
        levels = storey_drift.get(case)
        if not levels:
            continue
        eq = case.startswith("EQ")
        for lvl in sorted(levels):
            drift, h, cid = levels[lvl]
            ratio = drift / h if h > 0 else float("inf")
            rows.append({"Check": "Storey drift", "Case": case, "Direction": case[-1],
                         "Storey": "Ground storey" if lvl == 0 else f"Storey {lvl}", "Column": cid,
                         "Drift (mm)": round(drift * 1000.0, 2), "Height (mm)": round(h * 1000.0),
                         "Ratio": ratio, "Limit": EQ_DRIFT_LIMIT if eq else None,
                         "Status": ("FAIL" if ratio > EQ_DRIFT_LIMIT else "PASS") if eq else "INFO"})
        if not eq and case in top_displacement and total_height_m > 0:
            d, cid = top_displacement[case]
            ratio = d / total_height_m
            rows.append({"Check": "Top sway H/500", "Case": case, "Direction": case[-1], "Storey": "Top",
                         "Column": cid, "Drift (mm)": round(d * 1000.0, 2), "Height (mm)": round(total_height_m * 1000.0),
                         "Ratio": ratio, "Limit": WIND_TOP_SWAY_LIMIT,
                         "Status": "WARN" if ratio > WIND_TOP_SWAY_LIMIT else "PASS"})
    return rows


def is13920_column_geometry(columns, largest_beam_bar_mm: int) -> List[Tuple[str, str]]:
    """IS 13920:2016 7.1.1 (minimum dimension not less than 20 x the largest beam bar diameter or 300 mm) and
    7.1.2 as amended (Amd 1: smaller / larger dimension not less than 0.4). ``columns``: (id, b_mm, D_mm)."""
    out = []
    need = max(300.0, 20.0 * largest_beam_bar_mm)
    for cid, b, d in columns:
        issues = []
        if min(b, d) < need - 1e-6:
            basis = "300 mm" if need == 300.0 else f"20 x {largest_beam_bar_mm} mm beam bar = {need:.0f} mm"
            issues.append(f"least dimension {min(b, d):.0f} mm < {basis} (IS 13920 7.1.1)")
        if max(b, d) > 0 and min(b, d) / max(b, d) < 0.4 - 1e-9:
            issues.append(f"aspect ratio {min(b, d) / max(b, d):.2f} < 0.4 (IS 13920 7.1.2, Amd 1)")
        if issues:
            out.append((cid, "; ".join(issues)))
    return out


def eq_axial_stress_ratio(design_forces, b_mm: float, d_mm: float, fck: float) -> float:
    """Largest factored axial stress over the earthquake combinations divided by 0.40 fck
    (IS 13920:2016 7.1 as amended by Amendment 2); 0 when there is no earthquake combination."""
    pus = [f[1] for f in design_forces if "EQ" in f[0].upper()]
    if not pus or b_mm <= 0 or d_mm <= 0:
        return 0.0
    return max(pus) * 1000.0 / (b_mm * d_mm) / (0.40 * fck)


def _largest_bar(desc: str) -> int:
    import re
    return max((int(x) for x in re.findall(r"-(\d+)#", desc or "")), default=0)


def seismic_spec(gm: GridManager, seismic_result, inputs: "DesignInputs") -> SeismicSpec:
    """Floors (weight, centre of mass and polar radius of gyration from the slab panels) and the response
    spectrum of IS 1893 6.4.2(b) for the rigid-diaphragm 3D analysis (src/pseudo3d.py)."""
    from .pseudo3d import Floor
    from .seismic import SeismicDesignChecker, SeismicZone
    panels = gm.slab_panels() or [{"x0": 0.0, "x1": gm.width_m, "y0": 0.0, "y1": gm.length_m}]
    area = [(p["x1"] - p["x0"]) * (p["y1"] - p["y0"]) for p in panels]
    a_tot = sum(area) or 1.0
    xc = sum(a * (p["x0"] + p["x1"]) / 2 for a, p in zip(area, panels)) / a_tot
    yc = sum(a * (p["y0"] + p["y1"]) / 2 for a, p in zip(area, panels)) / a_tot
    r2 = sum(a * (((p["x0"] + p["x1"]) / 2 - xc) ** 2 + ((p["y0"] + p["y1"]) / 2 - yc) ** 2
                  + ((p["x1"] - p["x0"]) ** 2 + (p["y1"] - p["y0"]) ** 2) / 12.0) for a, p in zip(area, panels)) / a_tot
    floors = [Floor(weight_kn=w, xcm=xc, ycm=yc, r2=r2) for w in seismic_result.storey_weights_kn]
    p = seismic_result.parameters
    chk = SeismicDesignChecker(zone=SeismicZone(inputs.seismic_zone), soil_type=inputs.soil_type,
                               structural_system=inputs.structural_system)

    def ah_of_t(t):
        return p.zone_factor / 2.0 * p.importance_factor / p.response_reduction * \
            chk.get_spectral_acceleration(t, method="response_spectrum")
    cols = [c for c in gm.columns if c.level == 0] or gm.columns
    ext_x = (min(c.x for c in cols), max(c.x for c in cols))
    ext_y = (min(c.y for c in cols), max(c.y for c in cols))
    return SeismicSpec(method="response spectrum", floors=floors, static_forces=list(seismic_result.storey_forces_kn),
                       vb_static=seismic_result.base_shear_kn, ah_of_t=ah_of_t, extent_x=ext_x, extent_y=ext_y)


def _ll_factor(q: float) -> float:
    """IS 1893 (Part 1):2016 Table 10 - live load fraction for seismic weight."""
    return 0.25 if q <= 3.0 else 0.50


def run_design(gm: GridManager, beams: list, inputs: DesignInputs) -> DesignResults:
    from .seismic import check_soft_storeys, evaluate_joint_checks, run_seismic_check
    from .rebar_detailer import RebarDetailer  # noqa: F401
    messages: List[str] = []
    check_plan_geometry(gm, beams)          # input error before any calculation (non-finite / km-long geometry)

    lp = get_load_parameters(inputs.building_type_name)
    concrete = Concrete.from_grade(inputs.conc_grade)
    fck, fy = concrete.fck, inputs.fy
    gm.fck, gm.fy = fck, fy
    gm.num_stories = inputs.num_stories
    gm.story_height_m = inputs.story_height_m
    gm.slab_thickness_mm = float(lp.slab_thickness_mm)
    from .durability import requirements as durability_requirements
    dreq = durability_requirements(inputs.exposure, inputs.nbc_construction_type, fck)
    gm.beam_cover_mm, gm.slab_cover_mm = dreq.beam_cover_mm, dreq.slab_cover_mm
    gm.column_cover_mm, gm.footing_cover_mm = dreq.column_cover_mm, dreq.footing_cover_mm
    t = gm.slab_thickness_mm / 1000.0
    sdl = lp.floor_finish_kn_m2 + lp.partition_load_kn_m2 + lp.services_load_kn_m2
    gm.superimposed_dead_kn_m2 = sdl
    floor_dl = 25.0 * t + sdl
    floor_ll = lp.live_load_floor_kn_m2
    roof_dl = 25.0 * t + lp.floor_finish_kn_m2 + lp.services_load_kn_m2   # no partitions on the roof
    roof_ll = lp.live_load_roof_kn_m2
    ductile = inputs.structural_system.upper() in ("SMRF", "SMF")

    if not beams:
        beams = gm.generate_beams()
        messages.append("No beams supplied: beams generated along all grid lines")
    if not gm.walls and inputs.generate_walls_if_missing:
        gm.generate_walls(wall_thickness_mm=inputs.wall_core_thickness_mm, opening_fraction=inputs.wall_opening_fraction,
                          include_interior=inputs.include_interior_walls, slab_thickness_mm=gm.slab_thickness_mm)

    gm.boundary_segments = [((b.start_point.x, b.start_point.y), (b.end_point.x, b.end_point.y))
                            for b in beams if b.end_point is not None]

    staircase_bay = None
    if inputs.add_staircase and len(gm.x_grid_lines) > 1 and len(gm.y_grid_lines) > 1:
        staircase_bay = (max(0, min(len(gm.x_grid_lines) // 2, len(gm.x_grid_lines) - 2)),
                         max(0, min(len(gm.y_grid_lines) // 2, len(gm.y_grid_lines) - 2)))

    gm.calculate_trib_areas(staircase_bay=staircase_bay)
    load_kwargs = dict(wall_load_kn_m=inputs.wall_load_kn_m, dead_load_kn_m2=floor_dl, live_load_kn_m2=floor_ll,
                       roof_dead_kn_m2=roof_dl, roof_live_kn_m2=roof_ll)
    gm.calculate_loads(beams=beams, **load_kwargs)
    is_res = any(k in inputs.building_type_name.lower() for k in ("residential", "apartment", "housing", "flat", "dwelling"))
    gm.optimize_column_sizes(concrete=concrete, fy=fy, wall_thickness_mm=inputs.wall_core_thickness_mm,
                             align_to_wall=is_res if inputs.align_to_wall is None else inputs.align_to_wall,
                             seismic_zone=inputs.seismic_zone)
    for c in gm.columns:
        c.wall_dir = None
    if is_res if inputs.column_matches_wall is None else inputs.column_matches_wall:
        if inputs.seismic_zone != "II" or ductile:
            messages.append(f"Columns are at least 300 mm: IS 13920:2016 7.1.1 (minimum column dimension 300 mm) "
                            f"applies in Zone {inputs.seismic_zone} {'with SMRF' if ductile else ''}".rstrip() +
                            " (1.1.1: Zones III-V; SMRF relies on its detailing), so columns cannot match 230 mm walls")
        else:
            n_wall = apply_wall_width_columns(gm, beams, fck, fy)
            n_all = len({(round(c.x, 3), round(c.y, 3)) for c in gm.columns})
            messages.append(f"{n_wall} of {n_all} column positions stand in 230 mm wall lines and have a 230 mm side "
                            f"across the wall (D-29, Zone II OMRF; fire check IS 456 Fig. 1 '50 % exposed'). "
                            f"Free-standing columns stay at least 300 x 450 mm. Interior columns get 230 mm only "
                            f"where the model has interior walls (Masonry tab)")

    wind_result = None
    seismic_result = None
    summary = AnalysisSummary()
    building_weight = 0.0
    converged = False
    it = 0
    for it in range(1, inputs.max_iterations + 1):
        gm.calculate_loads(beams=beams, **load_kwargs)
        weights, heights, plan_area = storey_seismic_weights(gm, beams, _ll_factor)
        building_weight = sum(weights)
        seismic_result = run_seismic_check(
            gm.columns, beams, building_weight, zone=inputs.seismic_zone, building_type=inputs.building_type_name,
            fck=fck, height_m=heights[-1] if heights else inputs.num_stories * inputs.story_height_m,
            soil_type=inputs.soil_type, structural_system=inputs.structural_system,
            importance_factor=inputs.importance_factor, storey_weights_kn=weights, storey_heights_m=heights,
            base_dimension_m=max(gm.width_m, gm.length_m), masonry_infill=bool(gm.walls), fy=fy,
            plan_width_m=gm.width_m, plan_length_m=gm.length_m, plan_area_m2=gm.footprint_area_m2() or plan_area)
        lateral = LateralLoads(eq_x=seismic_result.storey_forces_kn, eq_y=seismic_result.storey_forces_kn)
        wind_result = None
        if inputs.wind_zone is not None:
            from .wind_load import TerrainCategory, calculate_wind_load
            wind_result = calculate_wind_load(
                zone=inputs.wind_zone, height_m=inputs.num_stories * inputs.story_height_m, width_m=gm.width_m,
                length_m=gm.length_m, terrain_category=inputs.terrain_category or TerrainCategory.CATEGORY_2,
                opening_percentage=inputs.wind_opening_percentage, storey_height_m=inputs.story_height_m)
            lateral.wl_x, lateral.wl_y = wind_result.storey_forces_x_kn, wind_result.storey_forces_y_kn

        summary = update_structural_analysis(gm, beams, fck=fck, use_cracked_sections=inputs.use_cracked_sections,
                                             fixed_base=inputs.fixed_base, lateral=lateral,
                                             seismic=seismic_spec(gm, seismic_result, inputs))
        before_beams = [(b.properties.width_mm, b.properties.depth_mm) for b in beams]
        gm.detail_beams(beams, fck=fck, fy=fy, ductile=ductile)
        gm.detail_columns(concrete, fy=fy, ductile=ductile, le_factor=inputs.le_factor)
        changed = before_beams != [(b.properties.width_mm, b.properties.depth_mm) for b in beams]
        # grow failing column stacks (stack-locked sizes)
        failing = {(round(c.x, 2), round(c.y, 2)) for c in gm.columns if gm.rebar_schedule[c.id].status == "FAIL"}
        # N16: seismic storey drift above the limit -> stiffen every column stack
        if any(r["Status"] == "FAIL" for r in drift_checks(summary.storey_drift, {}, 0.0)):
            failing |= {(round(c.x, 2), round(c.y, 2)) for c in gm.columns}
        for key in failing:
            stack = [c for c in gm.columns if (round(c.x, 2), round(c.y, 2)) == key]
            changed = _grow_stack(stack, gm.rebar_schedule.get(stack[0].id)) or changed
        # D-29: a beam designed wider than a wall column's 230 mm side (deep beams are 300 wide): widen the column
        for _bid, bw, cid, _across in beams_wider_than_columns(gm, beams):
            c0 = next(c for c in gm.columns if c.id == cid)
            if c0.wall_dir is None:
                continue
            stack = [c for c in gm.columns if (round(c.x, 2), round(c.y, 2)) == (round(c0.x, 2), round(c0.y, 2))]
            for c in stack:
                if c.wall_dir == "x":
                    c.depth_nb = next(float(p) for p in PREFERRED_COLUMN_SIZES if p >= bw)
                else:
                    c.width_nb = next(float(p) for p in PREFERRED_COLUMN_SIZES if p >= bw)
                c.wall_dir = None
            changed = True
        if not changed:
            converged = True
            break
    if not converged:
        messages.append(f"Design did not converge in {inputs.max_iterations} iterations - last results shown")

    # Final consistent pass after the last resize
    if not converged:
        gm.calculate_loads(beams=beams, **load_kwargs)
        summary = update_structural_analysis(gm, beams, fck=fck, use_cracked_sections=inputs.use_cracked_sections,
                                             fixed_base=inputs.fixed_base, lateral=lateral,
                                             seismic=seismic_spec(gm, seismic_result, inputs))
        gm.detail_beams(beams, fck=fck, fy=fy, ductile=ductile)
        gm.detail_columns(concrete, fy=fy, ductile=ductile, le_factor=inputs.le_factor)

    gm.detail_slabs(fck=fck, fy=fy)
    if inputs.add_staircase:
        gm.detail_staircase(fck=fck, fy=fy, live_load_kn_m2=lp.live_load_corridor_kn_m2)

    # Footings (service load incl. plinth walls; factored from the worst level-0 combination)
    level_0 = [c for c in gm.columns if c.level == 0]
    footings = []
    from .analysis_integration import build_combinations
    # N20: un-factor each combination's base moment by that combination's own
    # (largest) load factor, not by 1.5 for every combination
    combo_factor = {name: max(fac.values()) for name, fac in
                    build_combinations(True, inputs.wind_zone is not None) if fac}
    for col in level_0:
        service = col.load_kn + col.plinth_load_kn
        pu = max([f[1] for f in col.design_forces], default=1.5 * col.load_kn) + 1.5 * col.plinth_load_kn
        mbase = max([max(abs(f[2]), abs(f[3])) / combo_factor.get(f[0].rsplit("@", 1)[0], 1.5)
                     for f in col.design_forces if f[0].endswith("@bottom")], default=0.0)
        ft = design_footing(service, inputs.sbc_kn_m2, col.width_nb, col.depth_nb, concrete, fy=fy,
                            factored_load_kn=pu, base_moment_knm=mbase if inputs.fixed_base else 0.0,
                            clear_cover_mm=gm.footing_cover_mm)
        ft.id = f"F-{col.id}"
        footings.append(ft)
    gm.footings = footings
    overlap_msgs = check_footing_overlaps(level_0, footings)
    messages.extend(overlap_msgs)

    # Per-level beam copies (schedules keyed by plan id; lookups via gm.get_beam_result)
    all_beams = []
    for i in range(inputs.num_stories):
        for b in beams:
            cb = b.model_copy(deep=True)
            cb.id = f"{b.id}_L{i}"
            cb.level = i
            all_beams.append(cb)

    # Joint checks from the designed members
    seismic_result = evaluate_joint_checks(gm, beams, fck, fy, seismic_result)

    # Dynamic analysis actually performed (rigid-diaphragm 3D model, src/pseudo3d.py)
    sd = summary.seismic_design
    if "X" in sd:
        seismic_result.method_used = "response spectrum (7.7.5), 3D rigid-diaphragm model with torsion (7.8)"
        seismic_result.dynamic = {
            "modes": [{"Mode": k + 1, "Period (s)": round(m.period_s, 3), "Type": m.kind,
                       "Mass X %": round(100 * m.mass_x, 1), "Mass Y %": round(100 * m.mass_y, 1)}
                      for k, m in enumerate(sd["modes"])],
            "regularity": sd["regularity"]}
        for d in ("X", "Y"):
            r = sd[d]
            seismic_result.dynamic[d] = {
                "VB static (kN)": round(seismic_result.base_shear_kn, 1),
                "VB dynamic (kN)": round(r.base_shear_dynamic_kn, 1), "Scale factor": round(r.scale_factor, 3),
                "VB design (kN)": round(r.base_shear_kn, 1), "Modes for 90 % mass": r.modes_for_90pc,
                "Mass in those modes %": round(100 * r.mass_90pc, 1), "Torsion ratio": round(r.torsion_ratio, 3),
                "Storey forces (kN)": [round(v, 1) for v in r.storey_forces_kn],
                "Max static eccentricity (m)": round(max(abs(e[0]) for e in r.eccentricity_m), 3)}
        messages.append("Seismic design forces from the response spectrum method (IS 1893 7.7.5) on a 3D "
                        "rigid-diaphragm model with design eccentricity (7.8.2): T1 = "
                        f"{sd['modes'][0].period_s:.2f} s; VB = {sd['X'].base_shear_kn:.0f} / {sd['Y'].base_shear_kn:.0f} "
                        f"kN along X / Y (scaled to the static VB where lower, 7.7.3)")
        seismic_result.warnings = [
            ("Equivalent static method not permitted for this building (IS 1893 7.7.1): the response spectrum method "
             "(7.7.5) was used, scaled to the static base shear (7.7.3).")
            if w.startswith("Equivalent static method NOT permitted") else w for w in seismic_result.warnings]
    elif sd.get("model") == "translation only":
        seismic_result.method_used = "equivalent static (7.6), translation only (no torsion)"

    from .bbs_report import generate_bbs_from_grid_manager
    from .quantifier import Quantifier
    from .wall_calculator import WallCalculator
    from .audit import StructuralAuditor
    from .stability import run_stability_check
    from .safety_warnings import run_safety_warnings_check

    project_bbs = generate_bbs_from_grid_manager(gm, all_beams, inputs.project_name)
    bom = Quantifier().calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=inputs.use_fly_ash, fck=fck)
    avg_beam_depth = sum(b.properties.depth_mm for b in beams) / len(beams) if beams else 400.0
    wall_bom = WallCalculator(mortar_ratio=inputs.mortar_ratio, wc_ratio=0.50,
                              opening_fraction=inputs.wall_opening_fraction).calculate_all(
        gm.walls, num_stories=inputs.num_stories, floor_height_m=inputs.story_height_m,
        slab_thickness_mm=gm.slab_thickness_mm, beam_depth_mm=avg_beam_depth)
    auditor = StructuralAuditor(gm, all_beams, footings, sbc_kn_m2=inputs.sbc_kn_m2, fck=fck, fy=fy)
    audit_results = auditor.run_audit()
    stab_checks, stab_summary = run_stability_check(
        gm.columns, beams, inputs.num_stories, inputs.story_height_m, column_cover_mm=gm.column_cover_mm,
        beam_cover_mm=gm.beam_cover_mm, requirements=dreq, slab_cover_mm=gm.slab_cover_mm,
        slabs=[(sid, r.thickness_mm) for sid, r in gm.slab_schedule.items()])
    safety_summary = run_safety_warnings_check(gm.columns, beams, gm.width_m, gm.length_m, fck, inputs.seismic_zone,
                                               joint_details=seismic_result.joint_details,
                                               cracked_sections_applied=inputs.use_cracked_sections, fy=fy)

    # ---- status aggregation (single source of truth for every screen) ----
    failures: List[Dict[str, str]] = []

    def add(member, kind, status, issue):
        failures.append({"Member": member, "Type": kind, "Status": status, "Issue": issue})

    # a non-finite global result means the analysis broke down: nothing derived from it can be used
    globals_ = {"Seismic weight W (kN)": building_weight, "Static base shear VB (kN)": seismic_result.base_shear_kn}
    globals_.update({f"Design base shear VB {d} (kN)": sd[d].base_shear_kn for d in ("X", "Y") if d in sd})
    for name, val in globals_.items():
        if not math.isfinite(val):
            add("Building", "Numerical failure", "FAIL", f"{name} is not a finite number: the analysis did not "
                f"produce a usable result; no member design of this run can be relied on. Check the geometry and loads.")

    for bid, r in gm.beam_schedule.items():
        if r.status != "PASS":
            add(bid, "Beam", r.status, "; ".join(r.warnings) or r.status)
    for cid, r in gm.rebar_schedule.items():
        if r.status != "PASS":
            add(cid, "Column", r.status, "; ".join(w for w in r.warnings if not w.startswith("Effective length")) or r.status)
    for sid, r in gm.slab_schedule.items():
        if r.status != "PASS":
            add(sid, "Slab", r.status, "; ".join(w for w in r.warnings if "Table 26" not in w and "One-way" not in w) or r.status)
    for k, r in gm.staircase_schedule.items():
        if r.status != "PASS":
            add(k, "Staircase", r.status, "; ".join(r.warnings))
    for bid, bw, cid, across in beams_wider_than_columns(gm, beams):
        add(bid, "Beam wider than column", "WARN",
            f"beam {bw:.0f} mm wide frames into {cid.replace('_L0', '')} with a {across:.0f} mm side: the outer beam "
            f"bars pass outside the column cage - widen the column or narrow the beam")
    lost = {c.id.replace("_L0", "") for c in gm.columns if c.level == 0 and c.wall_dir is None
            and min(c.width_nb, c.depth_nb) > WALL_COLUMN_MM and _column_wall_dirs(gm, c.x, c.y)
            and any(m.startswith(tuple(str(i) for i in range(10))) and "230 mm wall lines" in m for m in messages)}
    if lost:
        add(", ".join(sorted(lost)[:6]), "Column wider than wall", "WARN",
            f"{len(lost)} column(s) in 230 mm wall lines needed more than {WALL_COLUMN_MAX_LONG_MM:.0f} x 230 mm and "
            f"were enlarged on both sides: they project from the wall")
    # columns drawn in the DXF at a size other than the one designed: the drawing must be updated before issue
    changed: Dict[Tuple[Tuple[float, float], Tuple[int, int]], List[str]] = {}
    for c in gm.columns:
        drawn = gm.drawn_column_sizes_mm.get(f"{c.x:.3f},{c.y:.3f}") if c.level == 0 else None
        if drawn and (abs(drawn[0] - c.width_nb) > 1 or abs(drawn[1] - c.depth_nb) > 1):
            changed.setdefault((drawn, (round(c.width_nb), round(c.depth_nb))), []).append(c.id.replace("_L0", ""))
    for (drawn, designed), ids in sorted(changed.items(), key=lambda kv: -len(kv[1])):
        add(", ".join(ids[:6]) + (" ..." if len(ids) > 6 else ""), "Drawing vs design", "WARN",
            f"{len(ids)} column(s) drawn {drawn[0]:.0f} x {drawn[1]:.0f} mm are designed {designed[0]} x "
            f"{designed[1]} mm (minimum sizes, wall width or strength: see the column schedule). Update the drawing "
            f"before issue")
    for ft in footings:
        if ft.status != "PASS":
            add(ft.id, "Footing", ft.status, "; ".join(ft.warnings) or ("bearing" if not ft.bearing_ok else ft.status))
    for a in audit_results:
        if a.status == "FAIL":
            add(a.member_id, f"Audit: {a.check_name}", "FAIL", a.notes)
    for f in summary.failed_frames:
        add(f.split(":")[0], "Frame analysis", "FAIL", f)
    for d in seismic_result.scwb_details:
        if not d["pass"]:
            add(d["Joint"], "SCWB", "FAIL" if ductile else "WARN",
                f"sum Mc / sum Mb = {d['Ratio']} < 1.4" + ("" if ductile else " (advisory for OMRF)"))
    for j in seismic_result.joint_details:
        if not j["pass"]:
            add(j["joint"], "Joint shear", "FAIL" if ductile else "WARN",
                f"Vj {j['Vj_demand_kN']:.0f} > {j['Vj_capacity_kN']:.0f} kN" + ("" if ductile else " (advisory for OMRF)"))
    # Seismic method (IS 1893 7.7.1) - owner decision D-26: what the model cannot represent is a WARN with details
    from .seismic import IrregularityType
    irr = set(seismic_result.analysis_method_check.irregularities_found or [])
    flexible = [t.value for t in irr if t in (IrregularityType.RE_ENTRANT_CORNER, IrregularityType.FLOOR_OPENING)]
    if flexible:
        add("Building", "Seismic method", "WARN",
            f"{', '.join(flexible)}: IS 1893 Table 5 (Amendment 2) requires a 3D dynamic analysis with FLEXIBLE floor "
            f"diaphragms (in addition to the rigid one) to capture force concentrations at re-entrant corners / "
            f"openings. StructOptima's dynamic analysis assumes rigid floors: member forces near the corners and the "
            f"floor slabs (diaphragm forces, collectors, chords) are NOT designed. Check the building with a "
            f"flexible-diaphragm 3D model (ETABS / STAAD / SAP2000) before construction.")
    if "X" not in sd and not seismic_result.static_analysis_allowed:
        add("Building", "Seismic method", "WARN",
            seismic_result.analysis_method_check.reason + ". The 3D dynamic model could not be built because the "
            "floors are not restrained against rotation (fewer than two frame lines in a direction); equivalent "
            "static forces without torsion were used. Add frame lines or verify with an independent 3D dynamic "
            "analysis.")
    # Table 5(i) as amended (Amd 2): torsional irregularity, and Table 6(vii) (Amd 2): irregular modes
    if "X" in sd:
        reg = sd["regularity"]
        for d in ("X", "Y"):
            ratio = sd[d].torsion_ratio
            if ratio > 1.4:
                add("Building", "Torsional irregularity", "FAIL",
                    f"Along {d}: Delta_max / Delta_ave = {ratio:.2f} > 1.4 - the structural configuration shall be "
                    f"revised (IS 1893 Table 5(i), Amendment 2)")
            elif ratio > 1.2:
                ok = reg.t_torsion is not None and all(t is None or reg.t_torsion < t for t in (reg.t1x, reg.t1y))
                add("Building", "Torsional irregularity", "WARN" if ok else "FAIL",
                    f"Along {d}: Delta_max / Delta_ave = {ratio:.2f} (1.2-1.4): 3D dynamic analysis performed; "
                    f"fundamental torsional period {reg.t_torsion or 0:.2f} s "
                    + ("is below the first translational periods (Table 5(i), Amendment 2)" if ok else
                       f"is NOT below the first translational periods ({reg.t1x or 0:.2f} / {reg.t1y or 0:.2f} s): "
                       f"revise the configuration (Table 5(i), Amendment 2)"))
        low = [d for d, mfrac in (("X", reg.first3_mass_x), ("Y", reg.first3_mass_y)) if mfrac < 0.65]
        if low:
            add("Building", "Irregular modes", "FAIL",
                f"First three modes carry less than 65 % of the mass along {', '.join(low)} "
                f"({100 * reg.first3_mass_x:.0f} % / {100 * reg.first3_mass_y:.0f} %): IS 1893 Table 6(vii), Amendment 2")
        if inputs.seismic_zone in ("IV", "V") and reg.t1x and reg.t1y and \
                abs(reg.t1x - reg.t1y) < 0.1 * max(reg.t1x, reg.t1y):
            add("Building", "Irregular modes", "FAIL",
                f"Fundamental periods along X and Y ({reg.t1x:.2f} / {reg.t1y:.2f} s) are within 10 % of each other; "
                f"in Zones IV and V they shall differ by at least 10 % (IS 1893 Table 6(vii), Amendment 2; not "
                f"applicable to buildings with large podiums). Make the two directions' stiffness different.")
    if not seismic_result.system_permitted:   # S2
        add("Building", "Structural system", "FAIL",
            f"OMRF is not allowed in Zone {inputs.seismic_zone}: RC structures in Zones III, IV and V shall be ductile "
            f"(IS 1893 (Part 1):2016 Table 9, Note 1). Select SMRF and provide IS 13920 detailing.")
    for fc in seismic_result.floating_columns:   # S7
        add(fc.column_id, "Floating column", "FAIL",
            f"{fc.warning} Floating columns that are part of or support the lateral load resisting system are not "
            f"permitted (IS 1893 (Part 1):2016 Table 6(vi), Amendment 2).")
    for m in overlap_msgs:
        add("Footings", "Overlap", "WARN", m)

    # storey drift (N16) from the final analysis
    total_h = max((c.z_top for c in gm.columns), default=inputs.num_stories * inputs.story_height_m) - \
        min((c.z_bottom for c in gm.columns), default=0.0)
    drift_rows = drift_checks(summary.storey_drift, summary.top_displacement, total_h)
    for r in drift_rows:
        if r["Status"] in ("FAIL", "WARN"):
            add(f"{r['Storey']} ({r['Direction']})", "Storey drift" if r["Check"] == "Storey drift" else "Wind top sway",
                r["Status"], f"{r['Case']}: {r['Drift (mm)']:.1f} mm over {r['Height (mm)']:.0f} mm = {r['Ratio']:.5f} "
                             f"> limit {r['Limit']:.5f} (IS 1893 7.11.1.1 / IS 456 20.5)")
    # S5: soft storey, IS 1893 Table 6(i) as amended (Amd 2) - storey stiffness K = storey shear / storey drift
    # under the EQ case; a storey less stiff than the storey above is a soft storey.
    for case in ("EQX", "EQY"):
        r_dir = sd.get(case[-1])
        forces = r_dir.storey_forces_kn if r_dir is not None else seismic_result.storey_forces_kn
        levels = summary.storey_drift.get(case) or {}
        if len(forces) > 1 and all(levels.get(i) and levels[i][0] > 0 for i in range(len(forces))):
            ks = [sum(forces[i:]) / levels[i][0] for i in range(len(forces))]
            # D-27: computed V / drift stiffness varies by a few % along any frame; drops above 10 % are flagged
            for soft in check_soft_storeys(ks, tolerance=SOFT_STOREY_TOLERANCE):
                lvl = "Ground storey" if soft.storey == 0 else f"Storey {soft.storey}"
                worst = max(levels[i][0] / levels[i][1] for i in range(soft.storey + 1))
                dyn = r_dir is not None
                bad = worst > 0.002 or not dyn
                add(f"{lvl} ({case[-1]})", "Soft storey", "FAIL" if bad else "WARN",
                    f"Lateral stiffness {soft.stiffness:,.0f} kN/m is less than the storey above "
                    f"({soft.stiffness_above:,.0f} kN/m): soft storey per IS 1893 (Part 1):2016 Table 6(i) "
                    f"(Amendment 2). Requires dynamic analysis ({'performed' if dyn else 'NOT performed'}) and drift "
                    f"<= 0.2 % in this storey and below (largest {100 * worst:.3f} %)")
    if not any(r["Case"].startswith("EQ") for r in drift_rows):
        add("Building", "Storey drift", "WARN", "No seismic drift result (lateral analysis not solved)")
    # N19: columns without frame moments in one direction
    for cid, plane in summary.columns_one_plane.items():
        add(cid, "Frame analysis", "WARN", f"Column lies on no {'Y' if plane == 'YZ' else 'X'}-direction frame line: "
                                           f"no frame moments about that axis (minimum eccentricity only)")
    # IS 13920 applies in Zones III, IV and V (1.1.1) and wherever R = 5 (SMRF) is relied on
    if ductile or inputs.seismic_zone != "II":
        h_total = max((c.z_top for c in gm.columns), default=inputs.num_stories * inputs.story_height_m)
        need = seismic_result.parameters.min_concrete_grade
        if fck < need:
            add("Building", "Concrete grade", "FAIL",
                f"M{int(fck)} is below the minimum M{need} for a {h_total:.1f} m building in Zone "
                f"{inputs.seismic_zone} (IS 13920:2016 5.2)")
        add("Building", "Reinforcement grade", "WARN",
            f"Fe{int(fy)} selected: IS 13920:2016 5.3.1 (Amd 2) requires elongation >= 14.5 % and TS / 0.2 % proof "
            f"stress between 1.15 and 1.25. IS 1786 minimums do not guarantee this (plain Fe 500: 12 % elongation) - "
            f"specify D-grade bars (Fe 415D / Fe 500D) and confirm from mill test certificates")
        beam_bar = max((max(_largest_bar(r.bottom_bars_desc), _largest_bar(r.top_bars_desc))
                        for r in gm.beam_schedule.values()), default=0)
        by_issue: Dict[str, List[str]] = {}
        for cid, issue in is13920_column_geometry([(c.id, c.width_nb, c.depth_nb) for c in gm.columns], beam_bar):
            by_issue.setdefault(issue, []).append(cid)
        for issue, ids in by_issue.items():
            add(", ".join(ids[:6]) + (f" (+{len(ids) - 6})" if len(ids) > 6 else ""), "Column geometry", "FAIL", issue)
        for c in gm.columns:
            ratio = eq_axial_stress_ratio(c.design_forces, c.width_nb, c.depth_nb, fck)
            if ratio > 1.0:
                add(c.id, "Column axial stress", "FAIL",
                    f"factored axial stress under earthquake combinations = {ratio * 0.40:.2f} fck > 0.40 fck "
                    f"(IS 13920:2016 7.1, Amd 2)")
    # IS 456 8.2.4.1 / Table 5: minimum grade for the exposure condition
    if fck < dreq.min_grade:
        add("Building", "Durability", "FAIL",
            f"M{int(fck)} is below the minimum M{dreq.min_grade} for '{inputs.exposure}' exposure "
            f"(IS 456:2000 Table 5; also max free w/c {dreq.max_wc}, min cement {dreq.min_cement_kg_m3} kg/m3)")
    # Fire resistance (NBC 2016 Part 4 Table 1 -> IS 456 Fig. 1 / Table 16A) and stability (IS 456 23.3, 25.3)
    fire_issues: Dict[Tuple[str, str], List[str]] = {}
    for chk in stab_checks:
        if not chk.is_fire_safe:
            fire_issues.setdefault((chk.member_type, chk.remarks), []).append(chk.member_id)
        if not chk.is_stable:
            add(chk.member_id, "Slenderness", "FAIL",
                f"{chk.member_type}: slenderness {chk.slenderness_ratio:.1f} > {chk.max_slenderness:.1f} "
                f"(IS 456 {'25.3.1' if chk.member_type == 'column' else '23.3'})")
    for (kind, remark), ids in fire_issues.items():
        add(", ".join(ids[:6]) + (f" (+{len(ids) - 6})" if len(ids) > 6 else ""), "Fire resistance", "FAIL",
            f"{kind}: {remark} - NBC type {inputs.nbc_construction_type} construction")
    if not inputs.use_cracked_sections:
        add("Building", "Stiffness modifiers", "WARN",
            "Gross section stiffness used: IS 1893 (Part 1):2016 6.4.3.1 requires 0.70 Igross for columns and "
            "0.35 Igross for beams in the structural analysis (drifts are under-estimated)")
    # N18: wind not considered
    if inputs.wind_zone is None:
        add("Building", "Wind", "WARN", "Wind loads not considered (no wind zone given)")
    for w in (getattr(wind_result, "warnings", None) or []):
        if w.startswith("UNCONSERVATIVE"):
            add("Building", "Wind", "FAIL", w)
        elif "dynamic (gust factor)" in w:
            add("Building", "Wind", "WARN", w)

    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    status = max([f["Status"] for f in failures] + ["PASS"], key=lambda s: order.get(s, 2))
    if not converged:
        status = "FAIL" if status == "FAIL" else "WARN"
    messages.extend(summary.messages)

    return DesignResults(
        gm=gm, beams=beams, all_beams=all_beams, footings=footings, bom=bom, wall_bom=wall_bom,
        audit_results=audit_results, auditor_math=auditor.math_breakdown, project_bbs=project_bbs,
        seismic_result=seismic_result, wind_result=wind_result, stab_checks=stab_checks, stab_summary=stab_summary,
        safety_summary=safety_summary, building_weight=building_weight, analysis_summary=summary, load_params=lp,
        iterations=it, converged=converged, status=status, failures=failures, messages=messages,
        drift_results=drift_rows)
