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

from .analysis_integration import AnalysisSummary, LateralLoads, update_structural_analysis
from .building_types import get_load_parameters
from .foundation_eng import Footing, check_footing_overlaps, design_footing
from .grid_manager import GridManager
from .logging_config import get_logger
from .materials import Concrete

logger = get_logger(__name__)

PREFERRED_COLUMN_SIZES = [230, 300, 350, 380, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000]

# Storey drift limit under the design lateral force with partial safety factor
# 1.0: IS 1893 (Part 1):2016 Cl 7.11.1.1 as commonly cited (0.004 h) - UNVERIFIED
# against the printed standard (docs/engineering/standards-register.md).
EQ_DRIFT_LIMIT = 0.004
# Lateral sway at the top under transient wind load: IS 456:2000 Cl 20.5 as
# commonly cited (H/500) - UNVERIFIED.  Serviceability -> WARN, not FAIL.
WIND_TOP_SWAY_LIMIT = 1.0 / 500.0

# Checks that are NOT performed, whatever the status says (gap analysis N17).
# Shown with every result so PASS cannot be read as complete engineering validation.
CHECKS_NOT_PERFORMED = [
    "3D analysis: torsion, accidental eccentricity and diaphragm flexibility (independent 2D frames only)",
    "Response-spectrum / dynamic analysis (equivalent static method only)",
    "Orthogonal seismic combination (100 % + 30 %) and vertical seismic action",
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
    use_fly_ash: bool = False
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
    beam_w = sum(b.properties.width_mm / 1000.0 * max(b.properties.depth_mm / 1000.0 - t, 0.0) * 25.0 *
                 math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
                 for b in beams if b.end_point is not None)
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


def _ll_factor(q: float) -> float:
    """IS 1893 (Part 1):2016 Table 10 - live load fraction for seismic weight."""
    return 0.25 if q <= 3.0 else 0.50


def run_design(gm: GridManager, beams: list, inputs: DesignInputs) -> DesignResults:
    from .seismic import evaluate_joint_checks, run_seismic_check
    from .rebar_detailer import RebarDetailer  # noqa: F401
    messages: List[str] = []

    lp = get_load_parameters(inputs.building_type_name)
    concrete = Concrete.from_grade(inputs.conc_grade)
    fck, fy = concrete.fck, inputs.fy
    gm.fck, gm.fy = fck, fy
    gm.num_stories = inputs.num_stories
    gm.story_height_m = inputs.story_height_m
    gm.slab_thickness_mm = float(lp.slab_thickness_mm)
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
                                             fixed_base=inputs.fixed_base, lateral=lateral)
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
            w, d = stack[0].width_nb, stack[0].depth_nb
            if max(w, d) >= 1500:
                continue
            nw, nd = _next_pref(w), _next_pref(d)
            for c in stack:
                c.width_nb, c.depth_nb = nw, nd
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
                                             fixed_base=inputs.fixed_base, lateral=lateral)
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
                            factored_load_kn=pu, base_moment_knm=mbase if inputs.fixed_base else 0.0)
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
    stab_checks, stab_summary = run_stability_check(gm.columns, beams, inputs.num_stories, inputs.story_height_m,
                                                    column_cover_mm=40.0, beam_cover_mm=25.0)
    safety_summary = run_safety_warnings_check(gm.columns, beams, gm.width_m, gm.length_m, fck, inputs.seismic_zone,
                                               joint_details=seismic_result.joint_details,
                                               cracked_sections_applied=inputs.use_cracked_sections, fy=fy)

    # ---- status aggregation (single source of truth for every screen) ----
    failures: List[Dict[str, str]] = []

    def add(member, kind, status, issue):
        failures.append({"Member": member, "Type": kind, "Status": status, "Issue": issue})

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
    if not seismic_result.static_analysis_allowed:
        add("Building", "Seismic method", "FAIL", seismic_result.analysis_method_check.reason)
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
                             f"> limit {r['Limit']:.5f} (limit value UNVERIFIED)")
    if not any(r["Case"].startswith("EQ") for r in drift_rows):
        add("Building", "Storey drift", "WARN", "No seismic drift result (lateral analysis not solved)")
    # N19: columns without frame moments in one direction
    for cid, plane in summary.columns_one_plane.items():
        add(cid, "Frame analysis", "WARN", f"Column lies on no {'Y' if plane == 'YZ' else 'X'}-direction frame line: "
                                           f"no frame moments about that axis (minimum eccentricity only)")
    # N18: wind not considered
    if inputs.wind_zone is None:
        add("Building", "Wind", "WARN", "Wind loads not considered (no wind zone given)")

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
