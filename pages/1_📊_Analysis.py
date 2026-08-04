import streamlit as st
import math
import sys, os
import pandas as pd

sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.ui_components import (
    inject_css, render_project_header, render_section_header, 
    render_metric_card, render_no_analysis_warning, 
    render_member_search, render_is_code_reference, render_status_badge
)
from src.stability import FIRE_RESISTANCE_TABLE
from src.load_combinations import LoadCombinationManager, get_summary_report

@st.cache_data(show_spinner="Optimizing structure...")
def run_optimization(_columns, story_height, num_stories, fck):
    from src.optimization import get_optimized_structure
    return get_optimized_structure(_columns, story_height, num_stories, fck)

st.set_page_config(page_title='StructOptima — Analysis', layout='wide', page_icon='📊')
inject_css()
render_project_header()
render_is_code_reference()

if not st.session_state.get('analysis_done'):
    render_no_analysis_warning()
    st.stop()

# Retrieve state
gm = st.session_state.get('gm')
all_beams = st.session_state.get('all_beams')
beams = st.session_state.get('beams')
bom = st.session_state.get('bom')
footings = st.session_state.get('footings')
seismic_result = st.session_state.get('seismic_result')
wind_result = st.session_state.get('wind_result')
stab_checks = st.session_state.get('stab_checks')
stab_summary = st.session_state.get('stab_summary')
safety_summary = st.session_state.get('safety_summary')
conc_grade = st.session_state.get('conc_grade')
fck = st.session_state.get('fck')
num_stories = st.session_state.get('num_stories')
story_height = st.session_state.get('story_height')
seismic_zone = st.session_state.get('seismic_zone')
building_weight = st.session_state.get('building_weight')
enable_optimization = st.session_state.get('enable_optimization')
building_type_name = st.session_state.get('building_type_name')
live_load = st.session_state.get('live_load')
m_grade = st.session_state.get('m_grade')
sorted_cols = st.session_state.get('sorted_cols')


# 1. Seismic Analysis section
render_section_header("Seismic Analysis — IS 1893:2016 / IS 13920:2016")

if seismic_result:
    st.info(
        f"**Zone {seismic_zone}** | "
        f"Z = {seismic_result.parameters.zone_factor} | "
        f"Ah = {seismic_result.parameters.design_acceleration:.3f} | "
        f"Base Shear = {seismic_result.base_shear_kn:.0f} kN"
    )
    
    if seismic_result.warnings:
        for warn in seismic_result.warnings:
            st.warning(warn)
            
    if seismic_result.parameters.scwb_required:
        z1, z2 = st.columns(2)
        with z1:
            if seismic_result.all_scwb_pass:
                st.success("✅ Strong Column-Weak Beam: PASS")
            else:
                st.error("❌ Strong Column-Weak Beam: FAIL (Some joints need review)")
        with z2:
            if seismic_result.all_ductile_pass:
                st.success(f"✅ Ductile Detailing: Ta={seismic_result.parameters.fundamental_period:.2f}s")
            else:
                st.warning("⚠️ Ductile Detailing: Review stirrup spacing")
                
    # Deep Beam Check
    if beams:
        deep_beams = [b for b in beams if hasattr(b, 'properties') and (math.hypot(b.end_point.x-b.start_point.x, b.end_point.y-b.start_point.y)*1000 / b.properties.depth_mm) < 2.0]
        if deep_beams:
            st.error(f"⚠️ DEEP BEAM DETECTED: {len(deep_beams)} beams have L/D < 2.0. Manual Strut & Tie check required.")
        
    if seismic_result.has_floating_columns:
        st.error(f"⚠️ {len(seismic_result.floating_columns)} FLOATING COLUMN(S) DETECTED")
        for fc in seismic_result.floating_columns:
            st.caption(fc.warning)
    else:
        st.success("✅ No floating columns - load path continuous")
        
    # Torsional Irregularity Check
    if gm and hasattr(gm, 'columns'):
        _level_0_cols_torsion = [c for c in gm.columns if c.level == 0]
        if _level_0_cols_torsion:
            _total_load = sum(c.load_kn for c in _level_0_cols_torsion)
            if _total_load > 0:
                _com_x = sum(c.x * c.load_kn for c in _level_0_cols_torsion) / _total_load
                _com_y = sum(c.y * c.load_kn for c in _level_0_cols_torsion) / _total_load
            else:
                _com_x = sum(c.x for c in _level_0_cols_torsion) / len(_level_0_cols_torsion)
                _com_y = sum(c.y for c in _level_0_cols_torsion) / len(_level_0_cols_torsion)
            
            _total_stiffness = sum(c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion)
            if _total_stiffness > 0:
                _cor_x = sum(c.x * c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion) / _total_stiffness
                _cor_y = sum(c.y * c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion) / _total_stiffness
            else:
                _cor_x, _cor_y = _com_x, _com_y
            
            _offset_x = abs(_com_x - _cor_x)
            _offset_y = abs(_com_y - _cor_y)
            _plan_x = gm.width_m
            _plan_y = gm.length_m
            
            _torsion_ratio_x = _offset_x / _plan_x if _plan_x > 0 else 0
            _torsion_ratio_y = _offset_y / _plan_y if _plan_y > 0 else 0
            _is_torsionally_irregular = _torsion_ratio_x > 0.05 or _torsion_ratio_y > 0.05
            
            if _is_torsionally_irregular:
                st.error(
                    f"🚨 **TORSIONAL IRREGULARITY DETECTED** (IS 1893 Cl. 7.1)\n\n"
                    f"CoM–CoR offset: X = {_offset_x:.3f}m ({_torsion_ratio_x:.1%} of plan), "
                    f"Y = {_offset_y:.3f}m ({_torsion_ratio_y:.1%} of plan)\n\n"
                    f"**The current 2D frame analysis cannot capture torsional response.** "
                    f"Story drift estimates may be unconservative by 2–3×. "
                    f"A full 3D analysis (ETABS/STAAD) is required for this layout."
                )
                st.warning(
                    "⚠️ **Drift-based checks are unreliable** for this configuration. "
                    "Do NOT use drift values from this analysis for compliance verification."
                )
            else:
                st.success(
                    f"✅ No torsional irregularity — CoM–CoR offset within 5% "
                    f"(X: {_torsion_ratio_x:.1%}, Y: {_torsion_ratio_y:.1%})"
                )
            
    with st.expander("View Ductile Detailing Requirements (IS 13920)"):
        if seismic_result.ductile_checks:
            ductile_data = []
            for dc in seismic_result.ductile_checks:
                ductile_data.append({
                    "Member": dc.member_id,
                    "Type": dc.member_type.title(),
                    "Hinge Zone (mm)": int(dc.hinge_zone_length_mm),
                    "Max Stirrup Spacing": f"{dc.max_stirrup_spacing_mm:.0f} mm",
                    "Min Stirrup Dia": f"{dc.min_stirrup_dia_mm} mm",
                    "Legs Required": dc.required_legs
                })
            st.dataframe(ductile_data)
            st.caption("📌 Plastic hinge zone: Use closer stirrup spacing at column/beam ends")
        else:
            st.info("Zone II - Ductile detailing not mandatory (recommended)")


# 2. Wind Analysis section
st.markdown("---")
render_section_header("Wind Analysis")

if wind_result and hasattr(wind_result, 'pressure_results') and wind_result.pressure_results:
    w1, w2, w3 = st.columns(3)
    w1.metric("Design Wind Speed (Top)", f"{wind_result.pressure_results[-1].design_wind_speed_ms:.1f} m/s")
    w2.metric("Wind Base Shear (X)", f"{wind_result.total_base_shear_x_kn:.0f} kN")
    w3.metric("Wind Base Shear (Y)", f"{wind_result.total_base_shear_y_kn:.0f} kN")
    
    if hasattr(wind_result, 'warnings') and wind_result.warnings:
        for w in wind_result.warnings:
            st.warning(w)


# 3. Stability & Fire Resistance section
st.markdown("---")
render_section_header("Stability & Fire Resistance (IS 456 Table 16A / NBC 2016)")

if stab_summary and stab_checks:
    fire_req = FIRE_RESISTANCE_TABLE[stab_summary.fire_rating_used]
    st.info(f"**Fire Rating Required:** {stab_summary.fire_rating_used.value} hours (based on {num_stories} floor building)")
    
    f1, f2, f3 = st.columns(3)
    f1.metric("Members Checked", stab_summary.total_members)
    f2.metric("Passed Stability", f"{stab_summary.passed_stability}/{stab_summary.total_members}")
    f3.metric("Passed Fire Check", f"{stab_summary.passed_fire}/{stab_summary.total_members}")
    
    if stab_summary.all_passed:
        st.success("✅ All members pass stability and fire resistance checks")
    else:
        st.warning(f"⚠️ {len(stab_summary.failed_members)} members need attention")
        if stab_summary.recommendations:
            for rec in stab_summary.recommendations:
                st.caption(f"📌 {rec}")
                
    with st.expander("View Fire Resistance Requirements (IS 456 Table 16A)"):
        st.markdown(f"""
        **Fire Rating: {stab_summary.fire_rating_used.value} hours** - {fire_req.description}
        
        | Member | Min Dimension | Min Cover |
        |--------|---------------|-----------|
        | Column | {fire_req.min_column_width_mm} mm | {fire_req.min_cover_column_mm} mm |
        | Beam | {fire_req.min_beam_width_mm} mm width | {fire_req.min_cover_beam_mm} mm |
        | Slab | {fire_req.min_slab_thickness_mm} mm thick | {fire_req.min_cover_slab_mm} mm |
        """)
        
    with st.expander("View All Stability Checks"):
        check_data = []
        for check in stab_checks:
            check_data.append({
                "Member": check.member_id,
                "Type": check.member_type.title(),
                "Slenderness": f"{check.slenderness_ratio:.1f} / {check.max_slenderness:.0f}",
                "Stab OK": "✓" if check.is_stable else "✗",
                "Dimension": f"{check.actual_dimension_mm} / {check.min_dimension_required_mm}",
                "Fire OK": "✓" if check.is_fire_safe else "✗",
                "Remarks": check.remarks
            })
        st.dataframe(check_data)


# 4. Advanced Safety Warnings section
st.markdown("---")
render_section_header("Advanced Structural Code Checks")

if safety_summary:
    if safety_summary.critical_warnings:
        for warn in safety_summary.critical_warnings:
            st.error(warn)
    else:
        st.success("✅ No critical plan irregularities detected")
        
    if safety_summary.recommendations:
        with st.expander("📝 Structural Recommendations", expanded=True):
            for rec in safety_summary.recommendations:
                st.markdown(f"- {rec}")
                
    with st.expander("View Joint Shear Capacity Checks (IS 13920)"):
        if safety_summary.joint_checks:
            joint_data = []
            for jc in safety_summary.joint_checks:
                joint_data.append({
                    "Joint": jc.joint_id,
                    "Type": "Interior",
                    "Shear Demand": f"{jc.joint_shear_demand_kn:.1f} kN",
                    "Capacity": f"{jc.joint_shear_capacity_kn:.1f} kN",
                    "Util%": f"{jc.utilization_ratio:.0%}",
                    "Status": "✅ OK" if jc.is_adequate else "❌ FAIL"
                })
            st.dataframe(joint_data)
            st.caption("Simplified check assuming typical reinforcement. Verify interior/exterior conditions.")
            
    with st.expander("Modelling Assumptions (Stiffness Modifiers)"):
        st.markdown("""
        **IS 1893 / IS 16700 Requirement:**
        For seismic analysis, use cracked section properties:
        
        | Member | Uncracked (Ig) | Cracked (Effective) |
        |--------|----------------|---------------------|
        | Columns | 1.0 Ig | **0.70 Ig** |
        | Beams | 1.0 Ig | **0.35 Ig** |
        | Slabs | 1.0 Ig | **0.25 Ig** |
        
        *Current analysis uses Gross Stiffness (Ig). Deflections may be 1.5-2x higher in reality.*
        """)


# 5. Load Combinations section
st.markdown("---")
render_section_header("Load Combinations (IS 875 Part 3 / IS 456 Table 18)")

if gm and num_stories is not None and live_load is not None and building_weight is not None:
    floor_area_m2 = gm.width_m * gm.length_m
    total_dl = building_weight - (floor_area_m2 * num_stories * live_load)
    total_ll = floor_area_m2 * num_stories * live_load
    
    total_wl = 0
    if wind_result and hasattr(wind_result, 'total_base_shear_x_kn'):
        total_wl = max(wind_result.total_base_shear_x_kn, wind_result.total_base_shear_y_kn)
        
    total_eq = 0
    if seismic_result and hasattr(seismic_result, 'base_shear_kn'):
        total_eq = seismic_result.base_shear_kn
        
    combo_mgr = LoadCombinationManager(
        include_wind=True,
        include_seismic=True,
        seismic_zone=seismic_zone if seismic_zone else "II"
    )
    
    with st.expander("View Governing Load Combinations & Stability Check", expanded=True):
        st.code(get_summary_report(combo_mgr, total_dl, total_ll, total_wl, total_eq), language="text")


# 6. Cost Optimization Results
if enable_optimization:
    st.markdown("---")
    render_section_header("Cost Optimization Results")
    
    if gm and hasattr(gm, 'columns') and story_height and num_stories and fck:
        opt_columns, opt_summary = run_optimization(
            gm.columns,
            story_height,
            num_stories,
            fck
        )
        
        if opt_summary.all_safe:
            st.success("✅ All optimized designs pass IS 456 safety checks")
        else:
            st.warning("⚠️ Some designs require review - using conservative sizing")
            
        s1, s2, s3 = st.columns(3)
        s1.metric(
            "Concrete Saved",
            f"{opt_summary.concrete_saved_m3:.2f} m³",
            f"{opt_summary.concrete_saved_pct:.1f}%"
        )
        s2.metric(
            "Steel Saved",
            f"{opt_summary.steel_saved_kg:.0f} kg",
            f"{opt_summary.steel_saved_pct:.1f}%"
        )
        s3.metric(
            "Cost Saved",
            f"₹{opt_summary.cost_saved:,.0f}",
            f"{opt_summary.cost_saved_pct:.1f}%"
        )
        
        with st.expander("View Optimized Column Sizes"):
            opt_data = []
            for col_id in sorted(opt_columns.keys()):
                oc = opt_columns[col_id]
                size_change = "→" if oc.original_size_mm != oc.optimized_size_mm else "="
                opt_data.append({
                    "Column": col_id,
                    "Level": oc.level,
                    "Original": f"{oc.original_size_mm[0]}×{oc.original_size_mm[1]}",
                    "→": size_change,
                    "Optimized": f"{oc.optimized_size_mm[0]}×{oc.optimized_size_mm[1]}",
                    "Load (kN)": f"{oc.axial_load_kn:.0f}",
                    "Capacity (kN)": f"{oc.design_capacity_kn:.0f}",
                    "D/C Ratio": f"{oc.dc_ratio:.2f}",
                    "Xu/d": f"{oc.xu_d_ratio:.2f}",
                    "Req vs Prov (cm²)": f"{oc.required_steel_mm2/100:.1f} / {oc.provided_steel_mm2/100:.1f}",
                    "Check": "✓" if oc.is_safe else "✗",
                    "Gov": "M_min" if oc.is_min_ecc_governed else "P_u"
                })
            st.dataframe(opt_data, width="stretch")
            st.caption("Gov: M_min = Governed by Minimum Eccentricity Check (< 0.05D)")


# 7. L/d Deflection Check
st.markdown("---")
render_section_header("L/d Deflection Check (IS 456 Cl 23.2)")

if beams:
    with st.expander("📐 Beam L/d Deflection Check (IS 456 Cl 23.2)", expanded=True):
        ld_data = []
        for b in beams:
            dx = b.end_point.x - b.start_point.x
            dy = b.end_point.y - b.start_point.y
            span_m = (dx**2 + dy**2)**0.5
            span_mm = span_m * 1000
            depth_mm = getattr(b.properties, 'depth_mm', 0) if hasattr(b, 'properties') else 0
            actual_ld = span_mm / depth_mm if depth_mm > 0 else 0
            
            allowable_ld = 7.0 if (hasattr(b.properties, 'is_cantilever') and getattr(b.properties, 'is_cantilever', False)) else 20.0
            status = "✅ OK" if actual_ld <= allowable_ld else "⚠️ Check"
            ld_data.append({
                "Beam": getattr(b, 'id', 'Unknown'),
                "Span (mm)": f"{span_mm:.0f}",
                "Depth (mm)": f"{depth_mm:.0f}",
                "Actual L/d": f"{actual_ld:.1f}",
                "Allowable L/d": f"{allowable_ld:.0f}",
                "Status": status
            })
        if ld_data:
            st.dataframe(pd.DataFrame(ld_data), width="stretch", hide_index=True)
            failed_ld = [d for d in ld_data if "Check" in d["Status"]]
            if failed_ld:
                st.warning(f"{len(failed_ld)} beam(s) exceed basic L/d ratio — verify modification factors per IS 456 Cl 23.2.1")
            else:
                st.success("All beams satisfy IS 456 Cl 23.2 basic L/d limits")
