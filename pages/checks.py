"""Checks: every design check grouped by topic, the failing items first."""
import math

import pandas as pd
import streamlit as st

from src.stability import FIRE_RESISTANCE_TABLE, rating_for_hours
from src.ui_components import page_title, require_results, style_status
from src.ui_tables import issue_rows


@st.cache_data(show_spinner="Optimizing structure...")
def run_optimization(_columns, _rebar_schedule, cache_key, story_height, num_stories, fck, fy, seismic_zone):
    """``cache_key`` is a hashable fingerprint of the columns and their design
    forces; the unhashed ``_columns`` argument alone previously produced stale
    results for new geometry (audit finding R22)."""
    from src.optimizer import optimize_structure
    return optimize_structure(_columns, story_height, num_stories, fck=fck, enable_optimization=True, fy=fy,
                              seismic_zone=seismic_zone, rebar_schedule=_rebar_schedule)


def _columns_fingerprint(columns):
    return tuple((c.id, round(c.x, 3), round(c.y, 3), c.level, c.width_nb, c.depth_nb, round(c.load_kn, 1),
                  tuple((f[0], round(f[1], 1), round(f[2], 1), round(f[3], 1)) for f in c.design_forces))
                 for c in columns)


require_results()
S = st.session_state
res = S['design_results']
gm = res.gm
beams = S.get('beams')
seismic_result = S.get('seismic_result')
wind_result = S.get('wind_result')
stab_checks = S.get('stab_checks')
stab_summary = S.get('stab_summary')
safety_summary = S.get('safety_summary')
num_stories = S.get('num_stories')
story_height = S.get('story_height')
seismic_zone = S.get('seismic_zone')
building_weight = S.get('building_weight')

page_title("Design checks", "Seismic, wind, drift, stability, joints and load combinations from the last design run. "
                            "Code values were compared with the printed standards on 2026-10-20 (standards check in "
                            "docs/verification); that is not an engineer's verification of this design.")

tabs = ["Issues", "Seismic", "Wind", "Drift", "Stability & fire", "Joints & plan", "Load combinations",
        "Deflection (L/d)"] + (["Optimisation"] if S.get("in_optimise") else [])
t = dict(zip(tabs, st.tabs(tabs)))

# ---- Issues (single source of truth: DesignResults.failures) ----
with t["Issues"]:
    st.markdown("#### Design Failures & Overstress Report")
    _failures = res.failures
    _fails = [f for f in _failures if f["Status"] == "FAIL"]
    _warns = [f for f in _failures if f["Status"] == "WARN"]
    if _fails:
        st.error(f"**{len(_fails)} failing item(s)** — the design is not acceptable as is.")
    if _warns:
        st.warning(f"**{len(_warns)} item(s) need engineering review**")
    if _failures:
        df = pd.DataFrame(issue_rows(_failures))[["Status", "Type", "Member", "Issue"]]
        st.dataframe(style_status(df), hide_index=True, height=min(38 + 35 * len(df), 600),
                     column_config={"Issue": st.column_config.TextColumn(width="large")})
    else:
        st.success("No failing or warning items among the implemented checks. This is not a substitute for "
                   "independent verification.")
    if seismic_result is not None and getattr(seismic_result, 'scwb_details', None):
        with st.expander("Strong column – weak beam details (all joints)"):
            st.dataframe(pd.DataFrame(seismic_result.scwb_details), hide_index=True)
            st.caption("ΣMc: column capacities at the smallest factored axial load; ΣMb: beam capacities from provided "
                       "steel (slab steel ignored). Required ratio 1.4.")

# ---- Seismic ----
with t["Seismic"]:
    if seismic_result:
        p = seismic_result.parameters
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Zone factor Z", p.zone_factor, help=f"Zone {seismic_zone}", border=True)
        m2.metric("Design acceleration Ah", f"{p.design_acceleration:.3f}", border=True)
        m3.metric("Base shear Vb", f"{seismic_result.base_shear_kn:.0f} kN", border=True)
        m4.metric("I / R", f"{p.importance_factor} / {p.response_reduction}", help=f"Soil type {p.soil_type}",
                  border=True)
        for warn in seismic_result.warnings or []:
            st.warning(warn)
        if p.scwb_required:
            z1, z2 = st.columns(2)
            with z1:
                _sd = getattr(seismic_result, 'scwb_details', []) or []
                if not getattr(seismic_result, 'scwb_evaluated', False):
                    st.info("Strong column – weak beam: not evaluated")
                elif seismic_result.all_scwb_pass:
                    st.success(f"Strong column – weak beam: {len(_sd)}/{len(_sd)} joints ΣMc ≥ 1.4 ΣMb (from designed "
                               f"members)")
                else:
                    st.error(f"Strong column – weak beam: {sum(1 for d in _sd if not d['pass'])}/{len(_sd)} joints "
                             f"below 1.4 ({'mandatory for SMRF' if S.get('structural_system') == 'SMRF' else 'advisory for OMRF'})")
            with z2:
                if getattr(seismic_result, 'ductile_verification', '') == "PARTIAL_SPACING_ONLY":
                    st.warning("Ductile detailing: end-zone tie spacing checked only — confining steel (Ash) and other "
                               "IS 13920 provisions NOT verified" + ("" if seismic_result.all_ductile_pass else
                                                                    " — some columns exceed the spacing limit"))
                else:
                    st.info(f"Ductile detailing: {getattr(seismic_result, 'ductile_verification', 'not evaluated')}")
        if seismic_result.has_floating_columns:
            st.error(f"{len(seismic_result.floating_columns)} floating column(s) detected")
            for fc in seismic_result.floating_columns:
                st.caption(fc.warning)
        else:
            st.success("No floating columns — vertical load path continuous")
        if getattr(seismic_result, 'storey_forces_kn', None):
            st.markdown("**Equivalent static storey forces (applied to the frame analysis)**")
            st.dataframe([{"Level": i + 1, "Height (m)": round(h, 2), "Seismic weight (kN)": round(w, 0),
                           "Storey force (kN)": round(f, 1)}
                          for i, (h, w, f) in enumerate(zip(seismic_result.storey_heights_m,
                                                            seismic_result.storey_weights_kn,
                                                            seismic_result.storey_forces_kn))], hide_index=True)
            st.caption("Forces shared between parallel frames by column stiffness; torsion not modelled.")
        with st.expander("Ductile detailing requirements (IS 13920)"):
            if seismic_result.ductile_checks:
                st.dataframe([{"Member": dc.member_id, "Type": dc.member_type.title(),
                               "Hinge zone (mm)": int(dc.hinge_zone_length_mm),
                               "Max stirrup spacing (mm)": round(dc.max_stirrup_spacing_mm),
                               "Min stirrup dia (mm)": dc.min_stirrup_dia_mm, "Legs": dc.required_legs}
                              for dc in seismic_result.ductile_checks], hide_index=True)
                st.caption("Plastic hinge zone: closer stirrup spacing at column and beam ends.")
            else:
                st.info("Zone II — ductile detailing not mandatory (recommended).")

# ---- Wind ----
with t["Wind"]:
    if wind_result and getattr(wind_result, 'pressure_results', None):
        w1, w2, w3 = st.columns(3)
        w1.metric("Design wind speed (top)", f"{wind_result.pressure_results[-1].design_wind_speed_ms:.1f} m/s",
                  border=True)
        w2.metric("Base shear, wind along X", f"{wind_result.total_base_shear_x_kn:.0f} kN", border=True)
        w3.metric("Base shear, wind along Y", f"{wind_result.total_base_shear_y_kn:.0f} kN", border=True)
        st.caption("Wind storey forces are applied to the frame analysis as load cases WLX / WLY.")
        for w in getattr(wind_result, 'warnings', None) or []:
            st.warning(w)
    else:
        st.info("No wind results.")

# ---- Drift (N16) ----
with t["Drift"]:
    _drows = getattr(res, 'drift_results', None)
    if _drows:
        _df = pd.DataFrame([{**r, "Ratio": f"{r['Ratio']:.5f}",
                             "Limit": "-" if r["Limit"] is None else f"{r['Limit']:.4f}"} for r in _drows])
        _bad = [r for r in _drows if r["Status"] in ("FAIL", "WARN")]
        if _bad:
            st.error(f"{len(_bad)} drift / sway check(s) exceed the limit — see the table.")
        else:
            st.success("All computed storey drifts are within the limits (IS 1893 7.11.1.1: 0.004 x storey height; "
                       "IS 456 20.5: H/500 under wind).")
        st.dataframe(style_status(_df), hide_index=True)
        st.caption("Drift = relative lateral displacement of the column ends in each storey under the unfactored design "
                   "lateral force (EQ: design base shear, includes 1/R; WL: design wind), from the 2D frame analysis "
                   "with the stiffness modifiers. EQ limit 0.004 x storey height (FAIL); wind: top sway H/500 (WARN), "
                   "storey values for information. No torsion or accidental eccentricity is included.")
    else:
        st.info("No drift results: run the analysis.")

# ---- Stability & fire ----
with t["Stability & fire"]:
    if stab_summary and stab_checks:
        _di = S.get('design_inputs')
        from src.durability import requirements as _req
        _r = _req(_di.exposure, _di.nbc_construction_type, S.get('fck', 25)) if _di is not None else None
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Column fire rating", f"{_r.column_fire_h:g} h" if _r else "-",
                  help=(f"NBC 2016 Part 4 Table 1, type {_di.nbc_construction_type} construction: columns supporting "
                        f"more than one floor {_r.column_fire_h:g} h, top-storey columns {_r.top_column_fire_h:g} h, "
                        f"beams {_r.beam_fire_h:g} h, floors {_r.slab_fire_h:g} h") if _r else None, border=True)
        f2.metric("Members checked", stab_summary.total_members, border=True)
        f3.metric("Pass stability", f"{stab_summary.passed_stability}/{stab_summary.total_members}", border=True)
        f4.metric("Pass fire check", f"{stab_summary.passed_fire}/{stab_summary.total_members}", border=True)
        if stab_summary.all_passed:
            st.success("All members pass the stability and fire resistance checks")
        else:
            st.warning(f"{len(stab_summary.failed_members)} members need attention")
            for rec in stab_summary.recommendations or []:
                st.caption(rec)
        if _r is not None:
            _c, _b, _s = (FIRE_RESISTANCE_TABLE[rating_for_hours(h)] for h in (_r.column_fire_h, _r.beam_fire_h,
                                                                               _r.slab_fire_h))
            st.markdown(f"""
| Member | Fire rating (NBC Table 1) | Min dimension (IS 456 Fig. 1) | Min cover for fire (Table 16A) | Cover used |
|--------|------|---------------|-----------|-----------|
| Column (supporting > 1 floor) | {_r.column_fire_h:g} h | {_c.min_column_width_mm} mm | {_c.min_cover_column_mm} mm | {S['gm'].column_cover_mm:.0f} mm |
| Beam | {_r.beam_fire_h:g} h | {_b.min_beam_width_mm} mm width | {_b.min_cover_beam_mm} mm | {S['gm'].beam_cover_mm:.0f} mm |
| Slab | {_r.slab_fire_h:g} h | {_s.min_slab_thickness_mm} mm thick | {_s.min_cover_slab_mm} mm | {S['gm'].slab_cover_mm:.0f} mm |
""")
            st.caption(f"Exposure '{_di.exposure}': durability cover {_r.beam_cover_mm:.0f} / {_r.slab_cover_mm:.0f} / "
                       f"{_r.column_cover_mm:.0f} / {_r.footing_cover_mm:.0f} mm for beams / slabs / columns / footings "
                       f"(the larger of IS 456 Table 16 and 16A), minimum grade M{_r.min_grade} (Table 5).")
        with st.expander("All stability checks"):
            st.dataframe([{"Member": c.member_id, "Type": c.member_type.title(),
                           "Slenderness": f"{c.slenderness_ratio:.1f} / {c.max_slenderness:.0f}",
                           "Stability": "PASS" if c.is_stable else "FAIL",
                           "Dimension (mm)": f"{c.actual_dimension_mm} / {c.min_dimension_required_mm}",
                           "Fire": "PASS" if c.is_fire_safe else "FAIL", "Remarks": c.remarks}
                          for c in stab_checks], hide_index=True)

# ---- Joints & plan ----
with t["Joints & plan"]:
    if safety_summary:
        if safety_summary.critical_warnings:
            for warn in safety_summary.critical_warnings:
                st.error(warn)
        else:
            st.success("No critical plan irregularities detected by the plan screen")
        if safety_summary.recommendations:
            st.markdown("**Structural recommendations**")
            for rec in safety_summary.recommendations:
                st.markdown(f"- {rec}")

    # Centre of mass vs centre of column stiffness (screen only - torsion is not analysed)
    _cols0 = [c for c in gm.columns if c.level == 0]
    if _cols0:
        _total_load = sum(c.load_kn for c in _cols0)
        if _total_load > 0:
            _com_x = sum(c.x * c.load_kn for c in _cols0) / _total_load
            _com_y = sum(c.y * c.load_kn for c in _cols0) / _total_load
        else:
            _com_x = sum(c.x for c in _cols0) / len(_cols0)
            _com_y = sum(c.y for c in _cols0) / len(_cols0)
        _total_stiffness = sum(c.width_nb * c.depth_nb ** 3 for c in _cols0)
        if _total_stiffness > 0:
            _cor_x = sum(c.x * c.width_nb * c.depth_nb ** 3 for c in _cols0) / _total_stiffness
            _cor_y = sum(c.y * c.width_nb * c.depth_nb ** 3 for c in _cols0) / _total_stiffness
        else:
            _cor_x, _cor_y = _com_x, _com_y
        _rx = abs(_com_x - _cor_x) / gm.width_m if gm.width_m > 0 else 0
        _ry = abs(_com_y - _cor_y) / gm.length_m if gm.length_m > 0 else 0
        st.markdown("**Mass – stiffness offset screen (ground storey)**")
        if _rx > 0.05 or _ry > 0.05:
            st.error(f"Offset between the centre of column load and the centre of column stiffness exceeds 5 % of the "
                     f"plan: X {_rx:.1%}, Y {_ry:.1%}. The 2D frame analysis cannot capture torsional response; "
                     f"drifts and member forces may be unconservative. A 3D analysis (ETABS / STAAD) is required.")
        else:
            st.info(f"Offset between the centre of column load and the centre of column stiffness: X {_rx:.1%}, "
                    f"Y {_ry:.1%} of the plan (screen limit 5 %). This is a screen only — torsion and accidental "
                    f"eccentricity are not analysed, so it is not the IS 1893 torsional irregularity check.")

    if beams:
        deep = [b for b in beams if b.properties.depth_mm > 0 and
                math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y) * 1000
                / b.properties.depth_mm < 2.0]
        if deep:
            st.error(f"Deep beams: {len(deep)} beam(s) with L/D < 2.0 — strut-and-tie check required (not performed).")

    st.markdown("**Joint shear (IS 13920)**")
    _jd = getattr(seismic_result, 'joint_details', None) if seismic_result is not None else None
    if _jd:
        _conf = {1.5: "Beams on 4 faces", 1.2: "Beams on 3 faces / 2 opposite faces"}
        _jdf = pd.DataFrame([{
            "Joint": j["joint"], "Level": j["level"], "Direction": j["direction"],
            "Confinement": _conf.get(j["confinement_factor"], "Other (k = 1.0)"),
            "Shear demand (kN)": round(j['Vj_demand_kN'], 1), "Capacity (kN)": round(j['Vj_capacity_kN'], 1),
            "Utilisation": f"{j['utilization']:.0%}", "Status": "PASS" if j["pass"] else "FAIL"} for j in _jd])
        st.dataframe(style_status(_jdf), hide_index=True)
        st.caption("Demand from the designed beam reinforcement at each joint; capacity k·√fck·Aj with k by the number "
                   "of framing beams (IS 13920:2016 9.1, Amendment 2). Slab steel and column shear are not included; "
                   "advisory for OMRF.")
    else:
        st.info("Joint shear not evaluated (requires designed beam reinforcement).")

    with st.expander("Modelling assumptions (stiffness modifiers)"):
        st.markdown("""
| Member | Uncracked | Cracked (effective) |
|--------|-----------|---------------------|
| Columns | 1.0 Ig | **0.70 Ig** |
| Beams | 1.0 Ig | **0.35 Ig** |
| Slabs | 1.0 Ig | **0.25 Ig** |
""")
        if S.get('use_cracked'):
            st.caption("Current analysis: cracked modifiers APPLIED to columns (0.70) and beams (0.35) for all load "
                       "cases. Slab stiffness is not modelled.")
        else:
            st.caption("Current analysis: GROSS section stiffness (Ig) for all load cases.")

# ---- Load combinations ----
with t["Load combinations"]:
    _asum = S.get('analysis_summary')
    if _asum is not None:
        a1, a2, a3 = st.columns(3)
        a1.metric("Frames solved", f"{_asum.frames_solved}/{_asum.frames_total}", border=True)
        a2.metric("Combinations", len(_asum.combinations), border=True)
        a3.metric("Beams outside frames", len(_asum.beams_not_in_frame), border=True)
        st.code("\n".join(_asum.combinations), language="text")
        st.caption("Load cases: DL, LL (gravity, from slab panels, walls and self-weight), EQX/EQY (seismic storey "
                   "forces), WLX/WLY (wind storey forces). Beam envelopes = max sagging, hogging and shear over all "
                   "combinations and storeys; columns are designed for every combination at both ends.")
        for _f in _asum.failed_frames:
            st.error(f"Frame not solved: {_f}")
        for _m in _asum.messages:
            st.caption(_m)
        if building_weight:
            from src.load_combinations import check_overturning
            _ot = 0.0
            if wind_result is not None:
                _ot = max(getattr(wind_result, 'total_overturning_moment_x_knm', 0),
                          getattr(wind_result, 'total_overturning_moment_y_knm', 0))
            if seismic_result is not None and seismic_result.storey_forces_kn:
                _ot = max(_ot, sum(f * h for f, h in zip(seismic_result.storey_forces_kn,
                                                         seismic_result.storey_heights_m)))
            _ok, _fos, _msg = check_overturning(building_weight, min(gm.width_m, gm.length_m), _ot)
            (st.success if _ok else st.error)(f"Overall overturning (0.9 W x B/2 vs 1.5 x M_ot): {_msg}")

# ---- L/d ----
with t["Deflection (L/d)"]:
    if beams:
        ld = []
        for b in beams:
            span_mm = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y) * 1000
            depth_mm = b.properties.depth_mm
            actual = span_mm / depth_mm if depth_mm > 0 else 0
            allowable = 7.0 if getattr(b.properties, 'is_cantilever', False) else 20.0
            ld.append({"Beam": b.id, "Span (mm)": round(span_mm), "Depth (mm)": round(depth_mm),
                       "Actual L/d": round(actual, 1), "Basic L/d": allowable,
                       "Status": "PASS" if actual <= allowable else "WARN"})
        _over = [d for d in ld if d["Status"] != "PASS"]
        if _over:
            st.warning(f"{len(_over)} beam(s) exceed the basic L/d ratio — check the modification factors "
                       f"(IS 456 Cl 23.2.1).")
        else:
            st.success("All beams satisfy the basic L/d limits (IS 456 Cl 23.2, modification factors not applied).")
        st.dataframe(style_status(pd.DataFrame(ld)), hide_index=True)

# ---- Optimisation ----
if "Optimisation" in t:
    with t["Optimisation"]:
        opt_columns, opt_summary = run_optimization(
            gm.columns, gm.rebar_schedule, _columns_fingerprint(gm.columns), story_height, num_stories, S.get('fck'),
            S.get('fy', 415.0), seismic_zone)
        st.warning("Indicative only: sizes are checked with member forces from the CURRENT analysis. A full re-analysis "
                   "and re-design with the optimised sizes is required before use; these sizes are not applied to the "
                   "model.")
        if opt_summary.all_safe:
            st.info("All proposed sizes pass the production column check under the current forces.")
        else:
            st.error("Some columns have no standard size passing the column check with the required margin.")
        s1, s2, s3 = st.columns(3)
        s1.metric("Concrete saved", f"{opt_summary.concrete_saved_m3:.2f} m³", f"{opt_summary.concrete_saved_pct:.1f}%")
        s2.metric("Steel saved", f"{opt_summary.steel_saved_kg:.0f} kg", f"{opt_summary.steel_saved_pct:.1f}%")
        s3.metric("Cost saved", f"₹{opt_summary.cost_saved:,.0f}", f"{opt_summary.cost_saved_pct:.1f}%")
        st.dataframe([{
            "Column": cid, "Level": oc.level,
            "Original": f"{oc.original_size_mm[0]}x{oc.original_size_mm[1]}",
            "Optimised": f"{oc.optimized_size_mm[0]}x{oc.optimized_size_mm[1]}",
            "Load (kN)": round(oc.axial_load_kn), "Capacity (kN)": round(oc.design_capacity_kn),
            "D/C": round(oc.dc_ratio, 2), "P-M ratio": round(oc.utilization_ratio, 2),
            "Steel req / prov (cm²)": f"{oc.required_steel_mm2 / 100:.1f} / {oc.provided_steel_mm2 / 100:.1f}",
            "Status": "PASS" if oc.is_safe else "FAIL", "Governs": "M_min" if oc.is_min_ecc_governed else "P_u"}
            for cid, oc in sorted(opt_columns.items())], hide_index=True)
        st.caption("Governs: M_min = design moment governed by minimum eccentricity / slenderness rather than the "
                   "analysis moments.")
