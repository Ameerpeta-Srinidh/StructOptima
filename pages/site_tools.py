import datetime

import pandas as pd
import streamlit as st

from src.ui_components import page_title, stale_notice
from src.ui_tables import BBS_SCOPE
from src.site_calculators import (
    calculate_rebar_weight, rebar_weight_table, concrete_pour_calculator, formwork_area_calculator,
    cube_test_summary, materials_for_mix, optimise_cutting, MIXER_CAPACITIES, REBAR_WEIGHT_PER_M,
)
from src.site_guide import SITE_CHECKLISTS
from src.bim_interop import CobieExporter
from src.site_inspection import DefectRecord, SiteInspectionManager

stale_notice()
page_title("Site tools", "Every number on this page is computed from the designed model or from data you enter. "
                         "Nothing is simulated or assumed. Outputs are PRELIMINARY — verify against the issued drawings.")

tab1, tab2, tab3, tab4 = st.tabs(["Bar Bending Schedule", "Site Calculators", "Site Checklists", "BIM & Handover"])

# ----------------- TAB 1: BBS -----------------
with tab1:
    if not st.session_state.get('analysis_done'):
        st.info("Run the design on the Setup page to generate the bar bending schedule.")
    else:
        st.markdown("#### Bar Bending Schedule")
        project_bbs = st.session_state.get('project_bbs')
        gm = st.session_state.get('gm')
        if not project_bbs or not gm:
            st.error("BBS data or structural model not found in session state.")
        else:
            st.markdown(f"**Steel in this schedule (cut lengths):** {project_bbs.total_steel_kg:,.1f} kg")
            st.caption(BBS_SCOPE)
            summary_data = []
            for dia in sorted(project_bbs.summary_by_diameter.keys()):
                wt = project_bbs.summary_by_diameter[dia]
                pct = (wt / project_bbs.total_steel_kg * 100) if project_bbs.total_steel_kg > 0 else 0
                summary_data.append({"Diameter (mm)": dia, "Weight (kg)": round(wt, 2), "% of Total": round(pct, 1)})
            st.dataframe(summary_data, width="stretch", hide_index=True)

            with st.expander("Detailed member-wise BBS"):
                for member in project_bbs.members:
                    st.text(f"{member.member_id} • {member.total_weight_kg:.2f} kg")
                    st.dataframe([{"Mark": e.bar_mark, "Dia": e.bar_diameter_mm, "Shape": e.shape_code,
                                   "Cut length (mm)": round(e.cutting_length_mm), "Nos": e.number_of_bars,
                                   "Wt (kg)": round(e.total_weight_kg, 2)} for e in member.entries],
                                  height=150, hide_index=True)

            st.markdown("#### Cutting plan from stock bars")
            stock_len = st.number_input("Stock bar length supplied (m)", min_value=6.0, max_value=15.0, value=12.0,
                                        step=0.5, help="Length of the bars delivered to site")
            pieces = [(e.bar_mark, int(e.bar_diameter_mm), e.cutting_length_mm / 1000.0, int(e.number_of_bars))
                      for m in project_bbs.members for e in m.entries]
            plan = optimise_cutting(pieces, stock_len)
            rows = [{"Dia (mm)": d, "Stock bars": v["stock_bars"], "Stock weight (kg)": v["stock_weight_kg"],
                     "Cut weight (kg)": v["cut_weight_kg"], "Offcut (m)": v["offcut_m"], "Efficiency %": v["efficiency_pct"]}
                    for d, v in plan["by_diameter"].items()]
            st.dataframe(rows, width="stretch", hide_index=True)
            st.caption("First-fit-decreasing plan: pieces are cut longest first from the fewest stock bars. "
                       "Offcuts are not reused across diameters.")
            if plan["needs_lap"]:
                st.warning(f"{len(plan['needs_lap'])} bar mark(s) are longer than the stock bar and need a lap or coupler "
                           "— locate laps as shown on the drawings / by the engineer:")
                st.dataframe(plan["needs_lap"], width="stretch", hide_index=True)
            sel_dia = st.selectbox("Show cutting plan for diameter", list(plan["by_diameter"].keys()) or [None])
            if sel_dia is not None:
                st.dataframe(plan["by_diameter"][sel_dia]["plan"], width="stretch", hide_index=True, height=250)
                st.download_button("⬇️ Cutting plan (CSV)", pd.DataFrame(plan["by_diameter"][sel_dia]["plan"]).to_csv(index=False),
                                   f"cutting_plan_{sel_dia}mm.csv", "text/csv", key="dl_cut_plan")

# ----------------- TAB 2: Calculators -----------------
with tab2:
    st.markdown("#### Site Calculators")
    calc_c1, calc_c2 = st.columns([1, 1])

    with calc_c1:
        with st.expander("Rebar Weight Calculator", expanded=True):
            r_dia = st.selectbox("Diameter", list(REBAR_WEIGHT_PER_M.keys()), format_func=lambda x: f"{x} mm")
            r_len = st.number_input("Length (m)", min_value=0.1, value=12.0)
            r_cnt = st.number_input("Count", min_value=1, value=1)
            wt_res = calculate_rebar_weight(r_dia, r_len, r_cnt)
            st.success(f"Total weight: **{wt_res['total_weight_kg']:.2f} kg** ({wt_res['unit_weight_kg_m']} kg/m)")
            if st.checkbox("Show unit weight table (d²/162)"):
                st.dataframe(rebar_weight_table(), width="stretch")

        with st.expander("Approved mix design", expanded=True):
            st.caption("Enter the batch weights per m³ of the mix approved for this project (lab trial mix / RMC "
                       "supplier). StructOptima does not assume a mix.")
            _m = st.session_state.get('approved_mix') or {}
            mix_name = st.text_input("Mix reference", value=_m.get('name', ''), placeholder="e.g. M25 lab mix 2026-10")
            m1, m2 = st.columns(2)
            cem = m1.number_input("Cement (kg/m³)", 0.0, 800.0, _m.get('cement_kg_m3'), placeholder="kg/m³")
            wat = m2.number_input("Water (kg/m³)", 0.0, 400.0, _m.get('water_kg_m3'), placeholder="kg/m³")
            fa = m1.number_input("Fine aggregate (kg/m³)", 0.0, 1500.0, _m.get('fine_aggregate_kg_m3'), placeholder="kg/m³")
            ca = m2.number_input("Coarse aggregate (kg/m³)", 0.0, 2000.0, _m.get('coarse_aggregate_kg_m3'), placeholder="kg/m³")
            if st.button("Save approved mix"):
                if None in (cem, wat, fa, ca) or not mix_name or cem <= 0:
                    st.error("Enter the mix reference and all four batch weights.")
                else:
                    st.session_state['approved_mix'] = {"name": mix_name, "cement_kg_m3": cem, "water_kg_m3": wat,
                                                        "fine_aggregate_kg_m3": fa, "coarse_aggregate_kg_m3": ca}
                    st.success(f"Saved. w/c = {wat / cem:.2f}. Used for material quantities on the dashboard, "
                               "pour planner and report.")

        with st.expander("Cube test register"):
            st.caption("Records cube results for a sample. Acceptance is judged by the engineer per IS 456 / IS 516.")
            c_grade = st.selectbox("Specified grade", ["M20", "M25", "M30", "M35", "M40"], index=1, key="cube_grade")
            k1, k2, k3 = st.columns(3)
            s1 = k1.number_input("Cube 1 (MPa)", 0.0, 100.0, None, key="cube1")
            s2 = k2.number_input("Cube 2 (MPa)", 0.0, 100.0, None, key="cube2")
            s3 = k3.number_input("Cube 3 (MPa)", 0.0, 100.0, None, key="cube3")
            age = st.number_input("Age at test (days)", 1, 365, 28)
            vals = [v for v in (s1, s2, s3) if v]
            if vals:
                cs = cube_test_summary(float(c_grade[1:]), vals)
                st.write(f"Mean **{cs['mean_mpa']} MPa** (min {cs['min_mpa']}, max {cs['max_mpa']}) at {age} days · "
                         f"mean / fck = {cs['mean_over_fck']} · largest deviation from mean {cs['max_deviation_from_mean_pct']} %")

    with calc_c2:
        with st.expander("Concrete Pour Planner", expanded=True):
            _bom = st.session_state.get('bom')
            vol_def = float(getattr(_bom, 'total_concrete_vol_m3', 0.0) or 1.0)
            vol = st.number_input("Net volume to pour (m³)", min_value=0.1, value=round(vol_def, 2),
                                  help="Defaults to the model's total wet volume when a design exists")
            mixer = st.selectbox("Transit mixer / mixer", list(MIXER_CAPACITIES.keys()))
            waste = st.slider("Wastage %", 0, 15, 3)
            rate = st.number_input("Pour rate achieved on site (m³/hr)", min_value=0.5, value=8.0)
            plan = concrete_pour_calculator(vol, MIXER_CAPACITIES[mixer], waste, rate, st.session_state.get('approved_mix'))
            p1, p2, p3 = st.columns(3)
            p1.metric("Gross volume", f"{plan['gross_volume_m3']:.2f} m³")
            p2.metric("Trips", plan['num_trips'])
            p3.metric("Pour time", f"{plan['estimated_pour_time_hr']:.1f} h")
            if "materials" in plan:
                mt = plan["materials"]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Cement", f"{mt['cement_bags']} bags")
                m2.metric("Fine agg.", f"{mt['fine_aggregate_t']:.2f} t")
                m3.metric("Coarse agg.", f"{mt['coarse_aggregate_t']:.2f} t")
                m4.metric("Water", f"{mt['water_l']:.0f} L")
            else:
                st.info("Save the approved mix (left) to get material quantities.")

        with st.expander("Formwork contact area"):
            if st.session_state.get('analysis_done'):
                gm = st.session_state.get('gm')
                all_beams = st.session_state.get('all_beams', [])
                slab_area = sum((p["x1"] - p["x0"]) * (p["y1"] - p["y0"]) for p in gm.slab_panels()) * gm.num_stories
                fw = formwork_area_calculator(columns=gm.columns, beams=all_beams, slab_area_m2=slab_area,
                                              slab_thickness_mm=gm.slab_thickness_mm)
                st.write(f"**Columns:** {fw['column_formwork_m2']:.1f} m² · **Beams:** {fw['beam_formwork_m2']:.1f} m² · "
                         f"**Slabs:** {fw['slab_formwork_m2']:.1f} m²")
                st.write(f"**Total contact area:** {fw['total_formwork_m2']:.1f} m² ≈ {fw['plywood_sheets_8x4']} sheets "
                         f"of 2.44 × 1.22 m (single use)")
                st.caption("Column and beam sides measured below the slab; overlaps at joints not deducted.")
            else:
                st.info("Complete the analysis to calculate formwork from the model.")

# ----------------- TAB 3: Checklists -----------------
with tab3:
    st.markdown("#### Site Checklists & Quick References")
    st.caption("Prompts for the inspecting engineer. Numerical values are as cited and UNVERIFIED against the printed "
               "standards; the project specification and the engineer's instructions govern.")
    
    for category, md_content in SITE_CHECKLISTS.items():
        with st.expander(f"{category}"):
            for i, line in enumerate(md_content.strip().split('\n')):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('- [ ] '):
                    item_text = line.replace('- [ ] ', '').strip()
                    st.checkbox(item_text, key=f"chk_{category}_{i}")
                else:
                    st.markdown(line)
                
                
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
    if not st.session_state.get('analysis_done') or st.session_state.get('design_results') is None:
        st.info("Run the design on the Setup page to enable these tools.")
    else:
        from src.documentation import calculation_summary
        from src.drawings import compute_marks
        from src.site_monitoring import (member_info, qr_png, qr_text, spectrum_from_csv, frequency_change,
                                         strain_from_csv, survey_from_csv)

        res = st.session_state['design_results']
        gm = res.gm
        project_name = st.session_state.get('project_name', 'Unnamed Project')
        engineer_name = st.session_state.get('engineer_name', '') or 'Not specified'
        marks = compute_marks(gm, res.beams, res.footings)
        member_ids = [c.id for c in gm.columns] + [b.id for b in res.beams] + [f.id for f in res.footings]

        ht1, ht2, ht3, ht4, ht5 = st.tabs(["Calculation Summary", "Member Tags (QR)", "Site Inspection",
                                           "Measured Vibration & Strain", "As-Built Survey"])

        with ht1:
            st.subheader("Calculation summary")
            st.caption("Built only from this design run: inputs, seismic parameters, storey drifts, the governing "
                       "column check, items needing attention and the checks StructOptima does not perform.")
            text = calculation_summary(res, project_name, engineer_name)
            st.text_area("Preview", text, height=360)
            st.download_button("Download calculation summary (.txt)", text, "Calculation_Summary.txt", "text/plain",
                               key="dl_calc_summary")

            st.markdown("#### COBie data (from the design)")
            cobie = CobieExporter(project_name)
            grade = f"M{gm.fck:.0f}"
            for c in gm.columns:
                tname = f"Column {c.width_nb:.0f}x{c.depth_nb:.0f}"
                if tname not in {t.name for t in cobie.types}:
                    cobie.add_type(tname, "Column", f"RCC column {grade}, Fe{gm.fy:.0f}")
                cobie.add_component(c.id, tname, f"Level_{c.level}", f"Mark {marks.columns.get(c.id, '')}")
                r = gm.rebar_schedule.get(c.id)
                cobie.add_attribute(c.id, "MainBars", r.main_bars_desc if r else "-", "")
                cobie.add_attribute(c.id, "ServiceLoad", f"{c.load_kn:.1f}", "kN")
                cobie.add_coordinate(c.id, c.x, c.y, c.z_bottom)
            for b in res.beams:
                r = gm.get_beam_result(b.id)
                if r is None:
                    continue
                tname = f"Beam {r.size_label}"
                if tname not in {t.name for t in cobie.types}:
                    cobie.add_type(tname, "Beam", f"RCC beam {grade}, Fe{gm.fy:.0f}")
                cobie.add_component(b.id, tname, "Typical floor", f"Mark {marks.beams.get(b.id, '')}")
                cobie.add_attribute(b.id, "Bars", f"T {r.top_bars_desc} / B {r.bottom_bars_desc} / {r.stirrups_desc}", "")
            st.download_button("Download COBie JSON", cobie.export_json(), "COBie_Data.json", "application/json",
                               key="dl_cobie")

        with ht2:
            st.subheader("Member tags")
            st.caption("Print and fix to formwork or the cage. The QR code holds the member's schedule as plain text "
                       "(readable offline by any phone camera).")
            sel = st.selectbox("Member", member_ids, key="qr_member")
            info = member_info(gm, res.beams, res.footings, marks, sel)
            q1, q2 = st.columns([1, 2])
            payload = qr_text(info, project_name, sel)
            png = qr_png(payload)
            q1.image(png, caption=f"{sel} ({info.get('Mark', '')})")
            q1.download_button("⬇️ QR (PNG)", png, f"QR_{sel}.png", "image/png", key="dl_qr")
            q2.table(pd.DataFrame(list(info.items()), columns=["Item", "Value"]))

        with ht3:
            st.subheader("Site inspection")
            site_mgr = SiteInspectionManager(project_name)
            i1, i2, i3 = st.columns(3)
            stage = i1.selectbox("Stage", ["Pre_Pour", "Post_Pour"])
            insp_member = i2.selectbox("Member", member_ids, key="insp_member")
            inspector = i3.text_input("Inspector", key="insp_name")
            items = site_mgr.generate_checklist(stage)
            for item in items:
                c1, c2, c3 = st.columns([4, 1, 2])
                c1.markdown(f"**{item.query}**  \nExpected: {item.expected_value} · Ref: {item.reference_code}")
                item.status = c2.selectbox("Result", ["Pending", "Pass", "Fail", "N/A"], key=f"chk_{stage}_{item.id}")
                item.remarks = c3.text_input("Remarks", key=f"rem_{stage}_{item.id}")
            st.download_button("⬇️ Checklist record (CSV)", SiteInspectionManager.checklist_csv(items, insp_member, inspector),
                               f"Inspection_{insp_member}_{stage}.csv", "text/csv", key="dl_checklist")

            st.markdown("#### Defect log")
            st.caption("Record what is observed. StructOptima does not diagnose causes or prescribe repairs — every "
                       "entry is marked for engineer review.")
            log = st.session_state.setdefault('defect_log', [])
            with st.form("defect_form", clear_on_submit=True):
                f1, f2, f3 = st.columns(3)
                d_member = f1.selectbox("Member", member_ids)
                d_type = f2.selectbox("Observed", ["Crack", "Honeycombing", "Exposed reinforcement", "Spalling",
                                                   "Misalignment", "Other"])
                d_loc = f3.text_input("Location on member", placeholder="e.g. 300 mm below top, east face")
                g1, g2, g3, g4 = st.columns(4)
                d_w = g1.number_input("Crack width (mm)", 0.0, 50.0, None)
                d_l = g2.number_input("Length (mm)", 0.0, 20000.0, None)
                d_lat = g3.number_input("Latitude (optional)", -90.0, 90.0, None, format="%.6f")
                d_lon = g4.number_input("Longitude (optional)", -180.0, 180.0, None, format="%.6f")
                d_notes = st.text_input("Notes")
                if st.form_submit_button("Add to log"):
                    try:
                        rec = site_mgr.record_defect(DefectRecord(d_member, d_type, d_loc, d_w, d_l,
                                                                  d_type == "Exposed reinforcement",
                                                                  inspector=inspector, notes=d_notes, lat=d_lat, lon=d_lon))
                        log.append(rec)
                    except ValueError as e:
                        st.error(str(e))
            site_mgr.defects = list(log)
            if log:
                st.dataframe([vars(d) for d in log], width="stretch", hide_index=True)
                st.download_button("⬇️ Defect log (CSV)", site_mgr.defects_csv(), "Defect_Log.csv", "text/csv",
                                   key="dl_defects")
                pts = site_mgr.get_defect_map_data()
                if pts:
                    st.map(pd.DataFrame(pts), latitude="lat", longitude="lon", zoom=16)
            else:
                st.info("No defects recorded.")

        with ht4:
            st.subheader("Measured vibration and strain")
            st.caption("Upload your own sensor records. Results are the arithmetic of your data; interpreting them "
                       "(e.g. damage) is for the engineer.")
            up = st.file_uploader("Accelerometer record (CSV: time s, acceleration)", type=["csv", "txt"], key="acc_csv")
            if up is not None:
                try:
                    spec = spectrum_from_csv(up.getvalue())
                    st.write(f"Sampling {spec['sampling_hz']:.1f} Hz, duration {spec['duration_s']:.1f} s, "
                             f"resolution {spec['resolution_hz']:.4f} Hz → dominant frequency **{spec['dominant_hz']:.3f} Hz**")
                    st.line_chart(pd.DataFrame({"Frequency (Hz)": spec["freq_hz"], "Amplitude": spec["amplitude"]}),
                                  x="Frequency (Hz)", y="Amplitude")
                    base = st.number_input("Baseline frequency from an earlier measurement (Hz)", 0.0, 100.0, None,
                                           key="base_f")
                    if base:
                        fc = frequency_change(spec["dominant_hz"], base)
                        st.write(f"Change {fc['change_pct']:+.1f} % · apparent stiffness ratio (f/f₀)² = "
                                 f"{fc['apparent_stiffness_ratio']:.3f} (same mass assumed)")
                except ValueError as e:
                    st.error(f"Cannot analyse the record: {e}")
            up2 = st.file_uploader("Strain gauge readings on reinforcement (CSV: gauge or member, microstrain)",
                                   type=["csv", "txt"], key="strain_csv")
            if up2 is not None:
                try:
                    st.dataframe(strain_from_csv(up2.getvalue(), gm.fy), width="stretch", hide_index=True)
                    st.caption(f"Yield strain = fy / Es = {gm.fy:.0f} / 200000 (Es = 200 kN/mm², IS 456 5.6.3).")
                except ValueError as e:
                    st.error(f"Cannot read the readings: {e}")

        with ht5:
            st.subheader("As-built column positions")
            st.caption("Upload the surveyed column centres (CSV: column id, x m, y m) in the design grid coordinates "
                       "and enter the specified positional tolerance.")
            tol = st.number_input("Specified positional tolerance (mm)", 0.0, 200.0, None, key="asb_tol")
            up3 = st.file_uploader("Survey CSV", type=["csv", "txt"], key="survey_csv")
            if up3 is not None:
                if not tol:
                    st.error("Enter the specified tolerance first.")
                else:
                    try:
                        sv = survey_from_csv(gm, up3.getvalue(), tol)
                        (st.error if sv["exceeding"] else st.success)(
                            f"{sv['exceeding']} of {len(sv['rows'])} surveyed columns exceed the tolerance.")
                        st.dataframe(sv["rows"], width="stretch", hide_index=True)
                        if sv["unknown_ids"]:
                            st.warning("Ids not in the design: " + ", ".join(sv["unknown_ids"]))
                        if sv["not_surveyed"]:
                            st.caption("Not surveyed: " + ", ".join(sv["not_surveyed"]))
                    except ValueError as e:
                        st.error(f"Cannot read the survey: {e}")
