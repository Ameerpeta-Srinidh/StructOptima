import streamlit as st
import pandas as pd
import math
import sys, os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.ui_components import inject_css, render_project_header, render_section_header, render_is_code_reference, render_metric_card
from src.site_calculators import (
    calculate_rebar_weight, rebar_weight_table, concrete_pour_calculator,
    formwork_area_calculator, curing_schedule, mix_design_table, MIXER_CAPACITIES, REBAR_WEIGHT_PER_M
)
from src.bbs_utils import BBSUtils, BendDeductionType, HookType
from src.site_guide import SITE_CHECKLISTS
from src.bim_interop import CobieExporter
from src.site_inspection import SiteInspectionManager
from src.shm_viz import SHMDashboard
from src.digital_twin import DigitalTwinExplorer
from src.documentation import DesignReportGenerator

st.set_page_config(page_title='StructOptima — Site Tools', layout='wide', page_icon='🔧')
inject_css()
render_project_header()
render_is_code_reference()

st.title("🔧 Site Tools & Execution Hub")
st.markdown("Practical tools for site engineers: BBS, checklists, estimators, and calculators.")

tab1, tab2, tab3, tab4 = st.tabs(["Bar Bending Schedule", "Site Calculators", "Site Checklists", "BIM & Handover"])

# ----------------- TAB 1: BBS -----------------
with tab1:
    if not st.session_state.get('analysis_done'):
        st.warning("⚠️ Please complete the structural analysis on the main page to generate the Bar Bending Schedule.")
    else:
        st.markdown("### Bar Bending Schedule & Optimization")
        
        project_bbs = st.session_state.get('project_bbs')
        gm = st.session_state.get('gm')
        all_beams = st.session_state.get('all_beams', [])
        
        if not project_bbs or not gm:
            st.error("BBS data or structural model not found in session state.")
        else:
            with st.expander("🛠️ BBS Analysis Settings", expanded=True):
                c_bbs1, c_bbs2, c_bbs3 = st.columns(3)
                
                with c_bbs1:
                    bbs_deduction_method = st.radio(
                        "Bend Deduction Method",
                        ["IS 2502 (Formula)", "SP 34 (Constants)"],
                        help="IS 2502 uses theoretical centerline. SP 34 uses simplified constants (e.g. 2d for 90°)."
                    )
                    use_sp34 = bbs_deduction_method == "SP 34 (Constants)"
                    
                with c_bbs2:
                    bbs_seismic_hooks = st.checkbox(
                        "Force 135° Seismic Hooks", 
                        value=True,
                        help="Mandatory for IS 13920 seismic detailing"
                    )
                    
                with c_bbs3:
                    stock_len = st.number_input(
                        "Rebar Stock Length (m)",
                        min_value=6.0,
                        max_value=15.0,
                        value=12.0,
                        step=0.5,
                        help="Standard commercial length for optimization"
                    )

            def parse_rebar_string(desc):
                try:
                    if not desc or desc == "-": return 0, 0
                    parts = desc.split('-')
                    num = int(parts[0])
                    dia_str = parts[1].replace('#', '').replace('mm', '').strip()
                    dia = int(dia_str)
                    return num, dia
                except:
                    return 0, 0

            all_cut_lists = []
            congestion_warnings = []
            
            for col in gm.columns:
                if hasattr(gm, 'rebar_schedule') and col.id in gm.rebar_schedule:
                    res = gm.rebar_schedule[col.id]
                    num_main, dia_main = parse_rebar_string(res.main_bars_desc)
                    
                    if num_main > 0:
                        cut_len_res = BBSUtils.calculate_cutting_length(
                            shape_code=0, 
                            dims_mm={"A": (gm.story_height_m * 1000) + (50 * dia_main)},
                            bar_dia_mm=dia_main,
                            bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502
                        )
                        
                        all_cut_lists.append({
                            "bar_mark": f"{col.id}-Main",
                            "dia": dia_main,
                            "length": cut_len_res.cutting_length_mm,
                            "count": num_main,
                            "weight": cut_len_res.cutting_length_mm * num_main * (dia_main**2/162) / 1000
                        })
                        
                    if res.links_desc:
                         try:
                             l_dia_str = res.links_desc.split('#')[0]
                             l_dia = int(l_dia_str)
                             l_spacing_str = res.links_desc.split('@')[1].split('c/c')[0].strip()
                             l_spacing = int(l_spacing_str)
                             
                             num_links = int((gm.story_height_m * 1000) / l_spacing)
                             
                             cov = 40 
                             dim_a = col.width_nb - 2*cov
                             dim_b = col.depth_nb - 2*cov
                             
                             hook_type = HookType.SEISMIC_135 if bbs_seismic_hooks else HookType.STANDARD_90
                             
                             cut_len_res = BBSUtils.calculate_cutting_length(
                                shape_code=51, 
                                dims_mm={"A": dim_a, "B": dim_b},
                                bar_dia_mm=l_dia,
                                bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502,
                                hook_type=hook_type
                             )
                             
                             all_cut_lists.append({
                                "bar_mark": f"{col.id}-Tie",
                                "dia": l_dia,
                                "length": cut_len_res.cutting_length_mm,
                                "count": num_links,
                                "weight": cut_len_res.cutting_length_mm * num_links * (l_dia**2/162) / 1000
                             })
                             
                         except:
                             pass

                    if "WARN" in res.congestion_status or "FAIL" in res.congestion_status:
                        congestion_warnings.append(f"Column {col.id}: {res.congestion_status}")

            for bm in all_beams:
                 if hasattr(gm, 'beam_schedule') and bm.id in gm.beam_schedule:
                     res = gm.beam_schedule[bm.id]
                     
                     n_bot, d_bot = parse_rebar_string(res.bottom_bars_desc)
                     if n_bot > 0:
                         l_m = ((bm.end_point.x-bm.start_point.x)**2 + (bm.end_point.y-bm.start_point.y)**2)**0.5
                         l_mm = l_m * 1000
                         
                         cut_len_res = BBSUtils.calculate_cutting_length(
                            shape_code=21, 
                            dims_mm={"A": l_mm + 50*d_bot}, 
                            bar_dia_mm=d_bot,
                            bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502,
                            hook_type=HookType.SEISMIC_135 if bbs_seismic_hooks else HookType.STANDARD_90
                         )
                         all_cut_lists.append({
                            "bar_mark": f"{bm.id}-Bot",
                            "dia": d_bot,
                            "length": cut_len_res.cutting_length_mm,
                            "count": n_bot,
                            "weight": cut_len_res.cutting_length_mm * n_bot * (d_bot**2/162) / 1000
                         })
                         
            st.markdown("#### ✂️ Cut Optimization (Stock Visualization)")
            if st.checkbox("Run Cutting Optimization"):
                opt_results = BBSUtils.optimize_cutting_from_stock(
                    all_cut_lists, 
                    stock_length_mm=stock_len*1000
                )
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Stock Bars Needed", opt_results.total_stock_bars)
                m2.metric("Total Wastage", f"{opt_results.total_wastage_pct:.1f}%")
                m3.metric("Offcuts Useful", len(opt_results.offcuts))
                
                with st.expander("View Cutting Patterns"):
                    for pattern in opt_results.cutting_patterns[:20]:
                        st.text(f"Stock Bar (Dia {pattern.bar_diameter_mm}mm): " + 
                                f" | ".join([f"{c['length']:.0f}mm ({c['mark']})" for c in pattern.cuts]) + 
                                f" [Rem: {pattern.remaining_length_mm:.0f}mm]")
                    if len(opt_results.cutting_patterns) > 20:
                        st.caption(f"... and {len(opt_results.cutting_patterns)-20} more patterns")

            if congestion_warnings:
                st.error(f"⚠️ {len(congestion_warnings)} Congestion Alerts")
                st.write(congestion_warnings)

            st.markdown("---")
            st.markdown(f"**Total Estimated Steel:** {project_bbs.total_steel_kg:.2f} kg (Pre-Optimization)")
            
            st.markdown("#### Steel Summary by Diameter")
            summary_data = []
            for dia in sorted(project_bbs.summary_by_diameter.keys()):
                wt = project_bbs.summary_by_diameter[dia]
                pct = (wt / project_bbs.total_steel_kg * 100) if project_bbs.total_steel_kg > 0 else 0
                summary_data.append({"Diameter (mm)": dia, "Weight (kg)": f"{wt:.2f}", "% of Total": f"{pct:.1f}%"})
            st.dataframe(summary_data)
            
            with st.expander("Detailed Member-wise BBS Report"):
                for member in project_bbs.members:
                    st.text(f"{member.member_id} • {member.total_weight_kg:.2f} kg")
                    entry_data = []
                    for e in member.entries:
                        entry_data.append({
                            "Mark": e.bar_mark,
                            "Dia": e.bar_diameter_mm,
                            "Shp": e.shape_code,
                            "L_cut": f"{e.cutting_length_mm:.0f}",
                            "Nos": e.number_of_bars,
                            "Wt": f"{e.total_weight_kg:.2f}"
                        })
                    st.dataframe(entry_data, height=150)

# ----------------- TAB 2: Calculators -----------------
with tab2:
    st.markdown("### Site Calculators (Standalone)")
    
    calc_c1, calc_c2 = st.columns([1, 1])
    
    with calc_c1:
        with st.expander("⚖️ Rebar Weight Calculator", expanded=True):
            r_dia = st.selectbox("Diameter", list(REBAR_WEIGHT_PER_M.keys()), format_func=lambda x: f"{x} mm")
            r_len = st.number_input("Length (m)", min_value=0.1, value=12.0)
            r_cnt = st.number_input("Count", min_value=1, value=1)
            if st.button("Calculate Rebar Weight"):
                wt = calculate_rebar_weight(r_dia, r_len, r_cnt)
                st.success(f"Total Weight: **{wt:.2f} kg**")
            
            if st.checkbox("Show Rebar Unit Weight Table (IS 1786)"):
                st.dataframe(rebar_weight_table(), width="stretch")

        with st.expander("🧪 Concrete Mix Design (IS 10262)"):
            grade = st.selectbox("Concrete Grade", ["M15", "M20", "M25", "M30", "M35", "M40"], index=2)
            if st.button("Get Proportions"):
                mix = mix_design_table(grade)
                st.write(f"**Proportions for {grade}**")
                st.dataframe(mix, width="stretch")

        with st.expander("💧 Curing Schedule"):
            c_grade = st.selectbox("Grade for Curing", ["M15", "M20", "M25", "M30", "M35", "M40"], index=2)
            st.dataframe(curing_schedule(c_grade), width="stretch")

    with calc_c2:
        with st.expander("🚛 Concrete Pour Planner", expanded=True):
            vol_def = 10.0
            if 'bom_results' in st.session_state and st.session_state.bom_results:
                vol_def = float(st.session_state.bom_results.get("Concrete Volume (m³)", 10.0))
            
            vol = st.number_input("Total Volume (m³)", min_value=0.1, value=vol_def)
            mixer = st.selectbox("Mixer Type", list(MIXER_CAPACITIES.keys()))
            waste = st.slider("Wastage %", 0, 15, 5)
            rate = st.number_input("Pour Rate (m³/hr)", min_value=1.0, value=20.0)
            
            if st.button("Calculate Pour Plan"):
                plan = concrete_pour_calculator(vol, mixer, waste, rate)
                p1, p2 = st.columns(2)
                p1.metric("Effective Volume", f"{plan['effective_volume']:.1f} m³")
                p1.metric("Trips Needed", plan['trips_needed'])
                p2.metric("Estimated Time", f"{plan['estimated_time_hrs']:.1f} hrs")
                
                st.markdown("**Materials Estimate:**")
                m1, m2, m3 = st.columns(3)
                m1.metric("Cement Bags", f"{plan['cement_bags']:.0f}")
                m2.metric("Sand", f"{plan['sand_tons']:.1f} t")
                m3.metric("Aggregate", f"{plan['aggregate_tons']:.1f} t")
                st.metric("Water", f"{plan['water_liters']:.0f} L")

        with st.expander("🪵 Formwork Estimator"):
            if st.session_state.get('analysis_done'):
                gm = st.session_state.get('gm')
                all_beams = st.session_state.get('all_beams', [])
                if st.button("Calculate from Model"):
                    fw = formwork_area_calculator(gm, all_beams)
                    st.write(f"**Column Formwork:** {fw['column_area']:.2f} m²")
                    st.write(f"**Beam Formwork:** {fw['beam_area']:.2f} m²")
                    st.write(f"**Total Area:** {fw['total_area']:.2f} m²")
                    st.info(f"Approx Plywood Sheets (2.44x1.22m): **{fw['plywood_sheets_needed']}**")
            else:
                st.info("Complete analysis to auto-calculate formwork from model.")

# ----------------- TAB 3: Checklists -----------------
with tab3:
    st.markdown("### Site Checklists & Quick References")
    
    for category, items in SITE_CHECKLISTS.items():
        with st.expander(f"📋 {category}"):
            for item in items:
                st.checkbox(item, key=f"chk_{category}_{item}")
                
    st.markdown("---")
    st.markdown("#### Engineering Sanity Checks & References")
    st.info("""
    - **Steel Density**: 7850 kg/m³
    - **Concrete Density**: 2400 kg/m³ (PCC) / 2500 kg/m³ (RCC)
    - **Cement Bag Weight**: 50 kg
    - **IS 456**: Code of Practice for Plain and Reinforced Concrete
    - **IS 13920**: Ductile Detailing of RC Structures
    - **IS 1786**: High Strength Deformed Steel Bars and Wires for Concrete Reinforcement
    """)

# ----------------- TAB 4: BIM & Handover -----------------
with tab4:
    if not st.session_state.get('analysis_done'):
        st.warning("⚠️ Please complete the structural analysis on the main page to enable BIM workflows.")
    else:
        st.markdown("### Construction & Handover Hub")
        st.info("Bridge the gap between Design and Execution with BIM L3 tools.")
        
        ht1, ht2, ht3, ht4, ht5 = st.tabs(["Design Reports", "BIM Export (COBie)", "Site Inspection", "SHM & IoT", "Digital Twin"])
        
        gm = st.session_state.get('gm')
        project_name = st.session_state.get('project_name', 'Unnamed Project')
        engineer_name = st.session_state.get('engineer_name', 'Site Engineer')
        seismic_result = st.session_state.get('seismic_result')
        
        with ht5:
            dt = DigitalTwinExplorer(project_name)
            
            st.subheader("🏙️ Interactive Digital Twin")
            st.markdown("Explore As-Built vs As-Designed states and access COBie metadata.")
            
            c_dt1, c_dt2 = st.columns([3, 1])
            
            with c_dt2:
                st.markdown("#### Controls")
                view_state = st.radio("Model State", ["As-Designed", "As-Built"], index=0)
                st.checkbox("Show MEP Systems", value=False)
                st.checkbox("Show Architectural", value=True)
                
                sel_elem = st.selectbox("Select Element to Inspect", [c.id for c in gm.columns] + ["B1", "B2"]) if gm else None
                
            with c_dt1:
                if sel_elem:
                    meta = dt.get_element_metadata(sel_elem)
                    st.info(f"**Selected:** {sel_elem}")
                    cols = st.columns(3)
                    for i, (k, v) in enumerate(meta.items()):
                        cols[i%3].metric(k, v)
                        
                    if view_state == "As-Built":
                        dev = dt.get_as_built_deviation(sel_elem)
                        st.warning(f"⚠️ As-Built Deviation: {dev['total_mm']}mm (dx:{dev['dx']}, dy:{dev['dy']}, dz:{dev['dz']})")
            
            st.markdown("#### 4D Construction Phasing")
            sim_date = st.date_input("Simulate Project Date")
            active_elems = dt.generate_construction_schedule_overlay(str(sim_date))
            st.write(f"Active Construction Elements: {', '.join(active_elems)}")
        
        with ht1:
            st.subheader("Structural Calculation Reports")
            st.markdown("Generate compliant design reports for peer review and municipal approval.")
            
            if st.button("Generate Detailed Design Report"):
                report_gen = DesignReportGenerator(project_name=project_name, engineer_name=engineer_name if engineer_name else "Not Specified")
                
                val_res = report_gen.validate_model(
                    modal_mass_percent=92.5, 
                    freq_hz=seismic_result.parameters.fundamental_period if seismic_result else 0.5
                )
                
                report_gen.check_storey_drift("Ground Floor", 8.0, 3000.0)
                report_gen.check_storey_drift("First Floor", 12.0, 3000.0)
                
                if gm and len(gm.columns) > 0:
                    report_gen.add_sample_calculation(
                        "Typical Column Design", "C1", 
                        [f"Pu = {gm.columns[0].load_kn:.1f} kN", "Mu = Min Eccentricity"], 
                        "IS 456 Cl 39.3"
                    )
                
                report_text = report_gen.generate_report()
                st.text_area("Report Preview", report_text, height=300)
                
                st.download_button(
                    label="📄 Download PDF Report",
                    data=report_text,
                    file_name="Detailed_Design_Report.txt",
                    mime="text/plain"
                )

        with ht2:
            st.subheader("COBie v3 Data Exchange")
            st.markdown("Export data for Facility Management (FM) software.")
            
            if st.button("Generate COBie Data"):
                cobie = CobieExporter(project_name)
                cobie.add_type("ResBeam", "Beam", "RCC Beam M25")
                cobie.add_type("ResCol", "Column", "RCC Column M25")
                
                if gm:
                    for c in gm.columns:
                        cobie.add_component(c.id, "ResCol", f"Level_{c.level}", "Structural Column")
                        cobie.add_attribute(c.id, "Load", f"{c.load_kn:.1f}", "kN")
                        cobie.add_coordinate(c.id, c.x, c.y, c.level * (gm.story_height_m if hasattr(gm, 'story_height_m') else 3.0))
                    
                cobie_json = cobie.export_json()
                st.success(f"Generated COBie dataset for {len(gm.columns) if gm else 0} components.")
                
                st.download_button(
                    label="📦 Download COBie JSON",
                    data=cobie_json,
                    file_name="COBie_Data.json",
                    mime="application/json"
                )
        
        with ht3:
            st.subheader("Site Inspection Checklists")
            st.markdown("Digital checklists for site engineers based on IS 13920.")
            
            stage = st.selectbox("Construction Stage", ["Pre_Pour", "Post_Pour"])
            site_mgr = SiteInspectionManager(project_name)
            checklist = site_mgr.generate_checklist(stage)
            
            st.write(f"**{stage} Checklist:**")
            for item in checklist:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{item.query}** (Ref: {item.reference_code})")
                c2.checkbox("Pass", key=f"chk_{item.id}")
                
            st.markdown("---")
            st.markdown("#### 🔍 AI & AR Site Tools")
            
            ar_col1, ar_col2 = st.columns(2)
            with ar_col1:
                st.info("📷 **AR Defect Overlay**")
                if st.button("Simulate AR Projection"):
                     st.image("https://via.placeholder.com/400x300.png?text=AR+Rebar+Overlay+Simulation", caption="Projected Rebar Cage")
            
            with ar_col2:
                st.info("📍 **Geo-Tagged Issue Map**")
                map_data = site_mgr.get_defect_map_data()
                if not map_data:
                    map_data = [{"lat": 12.9716, "lon": 77.5946, "type": "Crack", "severity": "Medium"}]
                st.map(data=[{"lat": d["lat"], "lon": d["lon"]} for d in map_data], zoom=15)
                
            st.markdown("#### QR Tagging")
            if gm and len(gm.columns) > 0:
                sel_qr = st.selectbox("Generate QR for", [c.id for c in gm.columns[:5]])
                st.code(site_mgr.generate_qr_code(sel_qr))
            else:
                st.info("No structural elements available to tag.")

        with ht4:
            st.subheader("📡 Smart SHM & IoT Dashboard")
            st.markdown("Real-time sensor data visualization and anomaly detection.")
            
            shm_viz = SHMDashboard(project_name)
            
            col_shm1, col_shm2 = st.columns([1, 2])
            
            with col_shm1:
                st.markdown("#### Structural Health Index")
                cur_freq = st.slider("Live Frequency (Hz)", 0.5, 2.0, 1.45, 0.01)
                base_freq = 1.5
                
                di_res = shm_viz.get_damage_index(cur_freq, base_freq)
                st.metric("Damage Index", f"{di_res['value']:.3f}", delta=di_res['message'], delta_color="inverse")
                
                st.progress(max(0.0, min(1.0, 1.0 - di_res['value'])), text="Health Score")
            
            with col_shm2:
                st.markdown("#### 📊 Vibration Spectrum (FFT)")
                fft_data = shm_viz.calculate_fft_spectrum(cur_freq)
                chart_data = pd.DataFrame({"Frequency (Hz)": fft_data['freq'], "Amplitude": fft_data['amp']})
                st.line_chart(chart_data, x="Frequency (Hz)", y="Amplitude")
            
            st.markdown("#### 🔥 Sensor Strain Heatmap")
            st.caption("Red zones indicate strain exceeding yield threshold.")
            heat_data = shm_viz.generate_heatmap_data(["C1", "C2", "B1", "B5"])
            st.write(heat_data)
