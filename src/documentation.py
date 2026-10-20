"""
Calculation summary built only from a design run (gap analysis N14).

``calculation_summary(res, project, engineer)`` returns a plain-text record of
the inputs, seismic parameters, storey drifts, the governing column check, the
failures list and the checks that are not performed - every number comes from
``DesignResults``.  Anything not computed by StructOptima (e.g. modal mass
participation - no modal analysis is done) is stated as not computed.
"""

from __future__ import annotations

from datetime import datetime
from typing import List


def calculation_summary(res, project_name: str, engineer_name: str) -> str:
    gm = res.gm
    L: List[str] = []
    bar = "=" * 72
    L += [bar, f"STRUCTURAL CALCULATION SUMMARY: {project_name}", f"Engineer: {engineer_name}",
          f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Design status: {res.status_label}", "PRELIMINARY - NOT FOR CONSTRUCTION", bar, ""]

    L += ["1. MODEL", "-" * 40,
          f"Plan {gm.width_m:.2f} x {gm.length_m:.2f} m, {gm.num_stories} storeys of {gm.story_height_m:.2f} m",
          f"Columns {len(gm.columns)} segments, beams {len(res.beams)} per floor, footings {len(res.footings)}",
          f"Concrete M{gm.fck:.0f}, steel Fe{gm.fy:.0f}",
          f"Floor DL {gm.dead_load_kn_m2:.2f} kN/m2, LL {gm.live_load_kn_m2:.2f} kN/m2 (occupancy slab "
          f"{gm.slab_thickness_mm:.0f} mm; thicker designed panels add their extra weight)",
          f"Design iterations {res.iterations}, converged: {'yes' if res.converged else 'NO'}", ""]

    s = res.seismic_result
    L += ["2. SEISMIC (equivalent static, IS 1893 Part 1 as implemented)", "-" * 40]
    if s is not None and getattr(s, "parameters", None) is not None:
        p = s.parameters
        L += [f"Zone factor Z = {p.zone_factor}, I = {p.importance_factor}, R = {p.response_reduction}, soil {p.soil_type}",
              f"Approximate period Ta = {p.fundamental_period:.3f} s, Ah = {p.design_acceleration:.4f}",
              f"Seismic weight W = {res.building_weight:.1f} kN, base shear Vb = {s.base_shear_kn:.1f} kN",
              "Storey forces (kN, bottom to top): " + ", ".join(f"{f:.1f}" for f in s.storey_forces_kn),
              "Modal analysis / modal mass participation: NOT COMPUTED (equivalent static method only)"]
    else:
        L.append("No seismic result.")
    L.append("")

    L += ["3. STOREY DRIFT (unfactored design lateral forces, 2D frames; limits IS 1893 7.11.1.1 and IS 456 20.5)", "-" * 40,
          f"{'Case':<5} {'Storey':<14} {'Column':<10} {'Drift mm':>9} {'H mm':>7} {'Ratio':>9} {'Limit':>7}  Status"]
    for r in res.drift_results:
        lim = "-" if r["Limit"] is None else f"{r['Limit']:.4f}"
        L.append(f"{r['Case']:<5} {r['Storey']:<14} {r['Column']:<10} {r['Drift (mm)']:>9.2f} {r['Height (mm)']:>7.0f} "
                 f"{r['Ratio']:>9.5f} {lim:>7}  {r['Status']}")
    if not res.drift_results:
        L.append("No drift results.")
    L.append("")

    L += ["4. GOVERNING COLUMN (largest interaction ratio)", "-" * 40]
    if gm.rebar_schedule:
        cid, r = max(gm.rebar_schedule.items(), key=lambda kv: kv[1].interaction_ratio)
        col = next((c for c in gm.columns if c.id == cid), None)
        size = f"{col.width_nb:.0f} x {col.depth_nb:.0f} mm" if col else "-"
        L += [f"Column {cid}, {size}, bars {r.main_bars_desc}, ties {r.links_desc}",
              f"Governing combination: {r.governing_combo}",
              f"Pu = {r.pu_design_kn:.1f} kN, Mux = {r.mux_design_knm:.1f} kNm, Muy = {r.muy_design_knm:.1f} kNm "
              f"(including minimum eccentricity / slenderness moments as designed)",
              f"Steel {r.steel_percent:.2f} %, interaction ratio {r.interaction_ratio:.3f}, status {r.status}"]
        L += [f"  {m}" for m in r.math_log[:25]]
    L.append("")

    L += ["5. ITEMS NEEDING ATTENTION", "-" * 40]
    for f in res.failures:
        L.append(f"[{f['Status']}] {f['Member']} - {f['Type']}: {f['Issue']}")
    if not res.failures:
        L.append("None reported by the implemented checks.")
    L.append("")

    L += ["6. CHECKS NOT PERFORMED BY STRUCTOPTIMA (do these separately)", "-" * 40]
    L += [f"- {c}" for c in res.checks_not_performed]
    L += ["", "All values are preliminary and NOT VERIFIED; independent verification by a licensed structural "
          "engineer is required before construction."]
    return "\n".join(L)
