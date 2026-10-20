"""Members: column, beam, slab and footing schedules, calculation logs and the masonry takeoff."""
import math

import pandas as pd
import streamlit as st

from src.ui_components import page_title, render_member_search, require_results, style_status
from src.ui_tables import beam_rows, column_rows, footing_rows, slab_rows

require_results()
S = st.session_state
res = S['design_results']
gm = res.gm
try:
    from src.drawings import compute_marks
    marks = compute_marks(gm, res.beams, list(res.footings))
except Exception:   # marks are labels only; schedules still show ids
    from src.drawings.marks import Marks
    marks = Marks()

page_title("Member schedules", "Sizes, reinforcement and status of every designed member. Marks (C1, B1, S1, F1) "
                               "match the drawing sheets.")
render_member_search()


def _table(rows, status_cols=("Status",), height=None, **config):
    if not rows:
        st.info("No members of this type in the design.")
        return
    df = pd.DataFrame(rows)
    n_fail = int((df["Status"] == "FAIL").sum()) if "Status" in df else 0
    n_warn = int((df["Status"] == "WARN").sum()) if "Status" in df else 0
    st.caption(f"{len(df)} members · {n_fail} FAIL · {n_warn} WARN")
    st.dataframe(style_status(df, status_cols), hide_index=True, column_config=config,
                 height=height or min(38 + 35 * len(df), 640))


t_col, t_beam, t_slab, t_foot, t_log, t_walls = st.tabs(
    ["Columns", "Beams", "Slabs", "Footings", "Calculation log", "Walls & finishes"])

with t_col:
    rows = column_rows(gm, marks)
    levels = sorted({r["Level"] for r in rows})
    f1, f2 = st.columns([1, 1])
    sel_levels = f1.pills("Level", levels, selection_mode="multi", default=levels, key="mem_levels",
                          format_func=lambda lv: "Ground" if lv == 0 else f"L{lv}")
    sel_status = f2.pills("Status", ["FAIL", "WARN", "PASS", "NOT DESIGNED"], selection_mode="multi",
                          default=["FAIL", "WARN", "PASS", "NOT DESIGNED"], key="mem_col_status")
    rows = [r for r in rows if r["Level"] in (sel_levels or []) and r["Status"] in (sel_status or [])]
    _table(rows, **{"P-M ratio": st.column_config.ProgressColumn(
        "P-M ratio", help="Governing biaxial interaction ratio from the column design (≤ 1.0 passes)",
        format="%.2f", min_value=0.0, max_value=1.0)})
    st.caption("Service load = unfactored axial load from the load takedown. The P-M ratio and status come from the "
               "column design for every factored combination.")

with t_beam:
    _table(beam_rows(gm, marks))
    st.caption("One row per plan beam (envelope over all storeys). Mu / Vu are the factored design actions.")

with t_slab:
    _table(slab_rows(gm, marks))
    st.caption("Slab panels of one typical floor; two-way moments from the IS 456 Table 26 coefficients as cited "
               "(checked against the printed table).")

with t_foot:
    _table(footing_rows(res.footings, marks), status_cols=("Bearing", "Punching", "One-way shear", "Bending", "Status"))
    st.caption("Isolated footings under the ground-storey columns, sized for the service load and the SBC entered on "
               "the Setup page; punching, one-way shear and bending checked for the factored load.")

with t_log:
    if getattr(gm, 'rebar_schedule', None):
        sel = st.selectbox("Column", list(gm.rebar_schedule.keys()), key="mem_log_col")
        log = gm.rebar_schedule[sel].math_log
        st.code("\n".join(log) if isinstance(log, list) else (log or "No calculation log recorded."), language="text")
    else:
        st.info("No column calculation logs.")

with t_walls:
    st.caption("Quantities calculated per IS 1077 (clay bricks), IS 2250 (mortar mixes), IS 1200 (opening deductions) "
               "and IS 1661 / IS 2402 (plastering), as cited — UNVERIFIED.")
    wall_bom = res.wall_bom
    if not wall_bom:
        st.info("The design has no wall quantities (no walls in the model).")
    else:
        wb = wall_bom
        num_stories = getattr(wb, 'num_stories', 1)
        tot_cem_bags = wb.total_mortar_cement_bags + wb.total_plaster_cement_bags
        tot_sand_t = wb.total_mortar_sand_tonnes + wb.total_plaster_sand_tonnes
        tot_water_l = wb.total_mortar_water_litres + wb.total_plaster_water_litres

        # Metric Cards
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            st.metric("Total Bricks", f"{wb.total_bricks:,} pcs")
            st.caption(f"Modular: 20×20×10 cm")
        with kpi2:
            st.metric("Total Cement", f"{tot_cem_bags:,} Bags")
            st.caption(f"{wb.total_mortar_cement_bags} Mortar + {wb.total_plaster_cement_bags} Plaster")
        with kpi3:
            st.metric("Total Sand", f"{tot_sand_t:.2f} Tonnes")
            st.caption(f"{wb.total_mortar_sand_tonnes:.2f}T Mortar + {wb.total_plaster_sand_tonnes:.2f}T Plaster")
        with kpi4:
            st.metric("Total Water", f"{tot_water_l:,.0f} L")
            st.caption(f"W:C = 0.50 (Mortar & Plaster)")
        with kpi5:
            st.metric("Plaster Area", f"{wb.total_plaster_area_m2:,.1f} m²")
            st.caption("Both sides (Ext 15mm / Int 12mm)")

        # Tabs for detailed breakdown
        w_tab1, w_tab2, w_tab3, w_tab4, w_tab5 = st.tabs([
            "Wall Sections", 
            "Brickwork Takeoff", 
            "Plastering Takeoff", 
            "Paint & Finishes", 
            "Formula Reference"
        ])

        with w_tab1:
            st.markdown("### Individual Wall Section Material Breakdown")
            st.caption(f"Detailed material quantities for every wall section across {num_stories} stories (Bricks, Mortar Wet/Dry, Cement, Sand, Water, Plaster, Paint).")
            wall_rows = []
            for sec in wb.wall_sections:
                wall_rows.append({
                    "Wall ID": sec.wall_id,
                    "Span": f"{sec.col_start}→{sec.col_end}" if (sec.col_start and sec.col_end) else "Bay",
                    "Type": "Exterior (230mm)" if sec.is_exterior else "Interior (115mm)",
                    "Length (m)": f"{sec.length_m:.2f}",
                    "Clear Ht (m)": f"{sec.clear_height_m:.2f}",
                    "Thk (mm)": int(sec.core_thickness_m * 1000),
                    "Vol (m³)": f"{sec.wall_volume_m3:.2f}",
                    "Bricks (Nos)": sec.num_bricks * num_stories,
                    "Wet Mortar (m³)": f"{sec.wet_mortar_vol_m3 * num_stories:.3f}",
                    "Dry Mortar (m³)": f"{sec.dry_mortar_vol_m3 * num_stories:.3f}",
                    "Mortar Cem (Bags)": int(math.ceil(sec.mortar_cement_kg * num_stories / 50.0)),
                    "Mortar Cem (kg)": f"{sec.mortar_cement_kg * num_stories:.1f}",
                    "Mortar Sand (T)": f"{sec.mortar_sand_tonnes * num_stories:.2f}",
                    "Water (L)": f"{(sec.mortar_water_litres + sec.plaster_water_litres) * num_stories:.0f}",
                    "Plaster (m²)": f"{sec.plaster_area_m2 * num_stories:.1f}",
                    "Plaster Cem (Bags)": int(math.ceil(sec.plaster_cement_kg * num_stories / 50.0)),
                    "Plaster Sand (T)": f"{sec.plaster_sand_tonnes * num_stories:.2f}",
                    "Primer (L)": f"{sec.primer_litres * num_stories:.1f}",
                    "Putty (kg)": f"{sec.putty_kg * num_stories:.1f}",
                    "Emulsion (L)": f"{(sec.emulsion_int_litres + sec.emulsion_ext_litres) * num_stories:.1f}",
                })
            if wall_rows:
                df_walls = pd.DataFrame(wall_rows)
                st.dataframe(df_walls, width="stretch", hide_index=True)
                csv_data = df_walls.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download Complete Wall Takeoff (CSV)",
                    data=csv_data,
                    file_name="Wall_Takeoff_Schedule.csv",
                    mime="text/csv",
                    key="download_wall_takeoff_csv"
                )

            st.markdown("#### Section Inspector")
            sel_wall_id = st.selectbox("Select Wall Section to Inspect", [s.wall_id for s in wb.wall_sections], key="select_inspect_wall")
            sel_sec = next((s for s in wb.wall_sections if s.wall_id == sel_wall_id), None)
            if sel_sec:
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1:
                    st.markdown("**Geometry**")
                    st.write(f"• Span: {sel_sec.col_start} → {sel_sec.col_end}")
                    st.write(f"• Type: {'Exterior (230mm)' if sel_sec.is_exterior else 'Interior (115mm)'}")
                    st.write(f"• Length: {sel_sec.length_m:.2f} m")
                    st.write(f"• Clear Height: {sel_sec.clear_height_m:.2f} m")
                    st.write(f"• Thickness: {int(sel_sec.core_thickness_m*1000)} mm")
                    st.write(f"• Gross Vol: {sel_sec.wall_volume_m3:.3f} m³")
                with sc2:
                    st.markdown("**Brickwork Takeoff**")
                    st.write(f"• Bricks (per floor): {sel_sec.num_bricks} Nos")
                    st.write(f"• Bricks (building total): {sel_sec.num_bricks * num_stories} Nos")
                    st.write(f"• Solid Brick Vol: {sel_sec.total_brick_vol_m3:.3f} m³")
                    st.write(f"• Wet Mortar: {sel_sec.wet_mortar_vol_m3:.3f} m³")
                    st.write(f"• Dry Mortar: {sel_sec.dry_mortar_vol_m3:.3f} m³")
                with sc3:
                    st.markdown("**Mortar & Plaster Materials**")
                    st.write(f"• Mortar Cement: {sel_sec.mortar_cement_kg:.1f} kg ({sel_sec.mortar_cement_bags} bags)")
                    st.write(f"• Mortar Sand: {sel_sec.mortar_sand_tonnes:.3f} T")
                    st.write(f"• Mortar Water: {sel_sec.mortar_water_litres:.1f} L")
                    st.write(f"• Plaster Area: {sel_sec.plaster_area_m2:.1f} m²")
                    st.write(f"• Plaster Cement: {sel_sec.plaster_cement_kg:.1f} kg ({sel_sec.plaster_cement_bags} bags)")
                    st.write(f"• Plaster Sand: {sel_sec.plaster_sand_tonnes:.3f} T")
                with sc4:
                    st.markdown("**Surface Coatings & Paint**")
                    st.write(f"• Primer (1 coat): {sel_sec.primer_litres:.2f} L")
                    st.write(f"• Putty (2 coats): {sel_sec.putty_kg:.1f} kg")
                    st.write(f"• Interior Emulsion: {sel_sec.emulsion_int_litres:.2f} L")
                    st.write(f"• Exterior Emulsion: {sel_sec.emulsion_ext_litres:.2f} L")

        with w_tab2:
            st.markdown("### Masonry & Brickwork Material Breakdown")
            m_data = [
                {"Material / Parameter": "Clay Bricks (Nominal Module 20×20×10 cm)", "Formula / Factor": "V_wall / 0.004 = 250 × V_wall", "Total Quantity": f"{wb.total_bricks:,}", "Unit": "Nos", "IS Standard": "IS 1077:1992"},
                {"Material / Parameter": "Total Wall Gross Volume", "Formula / Factor": "Σ (Length × Thickness × Clear Height)", "Total Quantity": f"{wb.total_wall_volume_m3:.2f}", "Unit": "m³", "IS Standard": "IS 1905:1987"},
                {"Material / Parameter": "Actual Solid Brick Volume (19×19×9 cm)", "Formula / Factor": "No. of bricks × 0.003249 m³", "Total Quantity": f"{sum(s.total_brick_vol_m3 for s in wb.wall_sections)*num_stories:.2f}", "Unit": "m³", "IS Standard": "IS 1077:1992"},
                {"Material / Parameter": "Wet Mortar Volume", "Formula / Factor": "V_wall − Solid Brick Volume", "Total Quantity": f"{sum(s.wet_mortar_vol_m3 for s in wb.wall_sections)*num_stories:.2f}", "Unit": "m³", "IS Standard": "IS 2250:1981"},
                {"Material / Parameter": "Dry Mortar Volume", "Formula / Factor": "Wet Volume × 1.33", "Total Quantity": f"{sum(s.dry_mortar_vol_m3 for s in wb.wall_sections)*num_stories:.2f}", "Unit": "m³", "IS Standard": "IS 2250:1981"},
                {"Material / Parameter": "Cement in Brickwork Mortar", "Formula / Factor": "Dry Vol × 1/(1+R) × 1440 kg/m³", "Total Quantity": f"{wb.total_mortar_cement_kg:,.0f} ({wb.total_mortar_cement_bags} bags)", "Unit": "kg (Bags)", "IS Standard": "IS 269 / IS 8112"},
                {"Material / Parameter": "Sand in Brickwork Mortar", "Formula / Factor": "Dry Vol × R/(1+R) × 1600 kg/m³", "Total Quantity": f"{wb.total_mortar_sand_tonnes:.2f}", "Unit": "Tonnes", "IS Standard": "IS 383:2016"},
                {"Material / Parameter": "Water for Masonry Mortar", "Formula / Factor": "0.50 × Weight of Cement", "Total Quantity": f"{wb.total_mortar_water_litres:,.0f}", "Unit": "Litres", "IS Standard": "IS 456 / IS 2250"},
            ]
            st.dataframe(pd.DataFrame(m_data), width="stretch", hide_index=True)

        with w_tab3:
            st.markdown("### Plastering Material Takeoff")
            p_data = [
                {"Application": "Internal Wall Plaster (Both/Inner Sides)", "Thickness": "12 mm (0.012 m)", "Mix Ratio": "1:6 (Cement : Sand)", "Dry Factor": "1.33", "IS Standard": "IS 1661:1972"},
                {"Application": "External Wall Plaster (Outer Face)", "Thickness": "15 mm (0.015 m)", "Mix Ratio": "1:4 (Cement : Sand)", "Dry Factor": "1.33", "IS Standard": "IS 2402:1963"},
                {"Application": "Total Plaster Area (All Stories)", "Thickness": "Both faces", "Mix Ratio": "-", "Dry Factor": f"{wb.total_plaster_area_m2:.1f} m²", "IS Standard": "IS 1200 Part 12"},
                {"Application": "Plastering Cement Required", "Thickness": "-", "Mix Ratio": "-", "Dry Factor": f"{wb.total_plaster_cement_kg:,.0f} kg ({wb.total_plaster_cement_bags} bags)", "IS Standard": "IS 269:2015"},
                {"Application": "Plastering Sand Required", "Thickness": "-", "Mix Ratio": "-", "Dry Factor": f"{wb.total_plaster_sand_tonnes:.2f} Tonnes", "IS Standard": "IS 383 Zone II/III"},
                {"Application": "Plastering Water Required", "Thickness": "-", "Mix Ratio": "W:C = 0.50", "Dry Factor": f"{wb.total_plaster_water_litres:,.0f} Litres", "IS Standard": "IS 456 Cl 5.4"},
            ]
            st.dataframe(pd.DataFrame(p_data), width="stretch", hide_index=True)

        with w_tab4:
            st.markdown("### Paint & Architectural Surface Coatings")
            paint_data = [
                {"Coating Layer": "Primer (Internal & External)", "Coats": f"{1} coat", "Film Thickness": "25–40 microns", "Coverage": "8 m²/Litre", "Total Required": f"{wb.total_primer_litres:.1f} Litres"},
                {"Coating Layer": "Wall Putty (Internal Faces)", "Coats": f"{2} coats", "Layer Thickness": "1–2 mm total", "Consumption": "1.5 kg/m²", "Total Required": f"{wb.total_putty_kg:,.1f} kg"},
                {"Coating Layer": "Interior Acrylic Emulsion", "Coats": f"{2} coats", "Film Thickness": "30–40 microns/coat", "Coverage": "12 m²/Litre", "Total Required": f"{wb.total_emulsion_int_litres:.1f} Litres"},
                {"Coating Layer": "Exterior Weather-Proof Emulsion", "Coats": f"{2} coats", "Film Thickness": "40–60 microns/coat", "Coverage": "10 m²/Litre", "Total Required": f"{wb.total_emulsion_ext_litres:.1f} Litres"},
            ]
            st.dataframe(pd.DataFrame(paint_data), width="stretch", hide_index=True)

        with w_tab5:
            st.markdown("### Mathematical Derivations & Engineering Logic")
            st.markdown("""
    ```text
    1. WALL GEOMETRY:
       - Clear Wall Height:  Hv = Hf - ts - Db
         where Hf = Floor-to-floor height, ts = Slab thickness, Db = Beam depth
       - Gross Wall Volume:  Vw = Length × Thickness × Hv

    2. BRICKWORK QUANTITIES (IS 1077 Modular Bricks):
       - Brick Size with mortar: 20 cm × 20 cm × 10 cm = 0.004 m³
       - Number of bricks:       Nb = Vw / 0.004 = 250 × Vw
       - Solid Brick Size:       19 cm × 19 cm × 9 cm = 0.003249 m³
       - Solid Brick Volume:     Vbrick = Nb × 0.003249 m³

    3. MORTAR CALCULATIONS (IS 2250):
       - Wet Mortar Volume:      Vm,wet = Vw - Vbrick
       - Dry Mortar Volume:      Vm,dry = Vm,wet × 1.33  (accounts for voids in dry ingredients)
       - Cement Volume:          Vc = Vm,dry × (1 / (1 + R))  where R = Sand parts in 1:R mix
       - Cement Mass:            Wc = Vc × 1440 kg/m³
       - Cement Bags:            Nb_bags = ceil(Wc / 50 kg)
       - Sand Volume:            Vs = Vm,dry × (R / (1 + R))
       - Sand Mass:              Ws = Vs × 1600 kg/m³  (Dry sand bulk density)
       - Sand Tonnes:            Ws / 1000
       - Water Mass:             Wwater = 0.50 × Wc  (W:C ratio = 0.50)

    4. PLASTERING QUANTITIES:
       - Internal Plaster:       12 mm thickness, 1:6 cement:sand mix
       - External Plaster:       15 mm thickness, 1:4 cement:sand mix
       - Dry Conversion:         Wet Plaster Volume × 1.33

    5. PAINT & SURFACE COATING:
       - Primer:                 1 coat (25–40 microns) @ 8 m²/L
       - Putty:                  2 coats (1–2 mm) @ 1.5 kg/m²
       - Interior Emulsion:      2 coats (30–40 microns) @ 12 m²/L
       - Exterior Emulsion:      2 coats (40–60 microns) @ 10 m²/L
    ```
    """)
