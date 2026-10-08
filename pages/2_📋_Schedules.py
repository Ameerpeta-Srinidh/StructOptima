import streamlit as st
import pandas as pd
import math
import sys, os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.ui_components import (inject_css, render_project_header, render_section_header, 
    render_member_search, render_no_analysis_warning, render_is_code_reference,
    render_dc_ratio_bar, render_status_badge)

st.set_page_config(page_title='StructOptima — Schedules', layout='wide', page_icon='📋')
inject_css()

if not st.session_state.get('analysis_done'):
    render_no_analysis_warning()
    st.stop()

render_project_header()

# 1. Member Search Bar
st.markdown("### 🔍 Quick Search")
render_member_search()
st.divider()

gm = st.session_state.get('gm')
footings = st.session_state.get('footings', {})
beams = st.session_state.get('beams', [])
level_0_cols = st.session_state.get('level_0_cols', [])
fck = st.session_state.get('fck', 25)

if not gm:
    st.error("Global Model not found.")
    st.stop()

# 2. Column Schedule
st.markdown("## Column Schedule")

# Group all columns by their level attribute
from collections import defaultdict
level_map = defaultdict(list)
for col in gm.columns:
    level_map[col.level].append(col)

all_levels = sorted(level_map.keys())

if all_levels:
    col1, col2 = st.columns(2)
    with col1:
        selected_level = st.selectbox("Select Level", ["All"] + [str(l) for l in all_levels])
    with col2:
        status_filter = st.selectbox("Status Filter", ["All", "Pass", "Warning", "Fail"])

    level_groups = all_levels if selected_level == "All" else [int(selected_level)]

    # Get ground-level columns for footing lookup (footings is a list parallel to level_0_cols)
    ground_cols = level_map.get(min(all_levels), [])
    footings_list = st.session_state.get('footings', [])

    for level in level_groups:
        render_section_header(f'Level {level} (Floor {level})')
        level_cols = level_map[level]

        data = []
        for col in level_cols:
            load = getattr(col, 'load_kn', 0)
            width = getattr(col, 'width_mm', getattr(col, 'width_nb', 300))
            depth = getattr(col, 'depth_mm', getattr(col, 'depth_nb', width))
            capacity = getattr(col, 'capacity_kn', getattr(col, 'capacity', 0))

            if capacity > 0:
                dc = load / capacity
            else:
                cap_est = (0.4 * fck * width * depth / 1000) + (0.67 * 415 * 0.008 * width * depth / 1000)
                dc = load / cap_est if cap_est > 0 else 0

            status = "Pass"
            if dc > 0.9:
                status = "Fail"
            elif dc >= 0.7:
                status = "Warning"

            if status_filter != "All" and status != status_filter:
                continue

            # Footing lookup (footings is a list indexed by ground column position)
            footing_size = "N/A"
            if level == min(all_levels):
                idx = next((i for i, gc in enumerate(ground_cols) if gc.id == col.id), None)
                if idx is not None and idx < len(footings_list):
                    f = footings_list[idx]
                    try:
                        footing_size = f"{f.length_m:.1f}x{f.width_m:.1f}x{f.thickness_mm/1000:.2f}m"
                    except AttributeError:
                        footing_size = str(f)

            main_steel = "N/A"
            stirrups = "N/A"
            if hasattr(gm, 'rebar_schedule') and gm.rebar_schedule and col.id in gm.rebar_schedule:
                rebar = gm.rebar_schedule[col.id]
                main_steel = getattr(rebar, 'main_bars_desc', getattr(rebar, 'main_steel', 'N/A'))
                stirrups = getattr(rebar, 'links_desc', getattr(rebar, 'stirrups', 'N/A'))

            h_col = getattr(col, 'z_top', 3.0) - getattr(col, 'z_bottom', 0.0)
            if h_col <= 0: h_col = 3.0
            col_conc_vol = (width / 1000.0) * (depth / 1000.0) * h_col
            col_steel_wt = col_conc_vol * 150.0  # IS 456 standard column steel ratio ~150 kg/m3

            data.append({
                "ID": col.id,
                "Size (mm)": f"{width:.0f}x{depth:.0f}",
                "Load (kN)": f"{load:.1f}",
                "Conc (m³)": f"{col_conc_vol:.2f}",
                "Steel (kg)": f"{col_steel_wt:.1f}",
                "D/C Ratio": min(dc, 1.0),
                "Main Steel": main_steel,
                "Stirrups": stirrups,
                "Footing Size": footing_size,
                "Status": status
            })

        if data:
            df = pd.DataFrame(data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "D/C Ratio": st.column_config.ProgressColumn(
                        "D/C Ratio",
                        help="Demand/Capacity Ratio",
                        format="%.2f",
                        min_value=0,
                        max_value=1.0,
                    ),
                }
            )
        else:
            st.info(f"No columns match filters for Level {level}.")
else:
    st.info("No columns available.")

st.divider()

# 3. Beam Schedule
st.markdown("## Beam Schedule")
beam_data = []
if hasattr(gm, 'beam_schedule') and gm.beam_schedule:
    for bid, b_info in gm.beam_schedule.items():
        if isinstance(b_info, dict):
            row = {k: str(v) for k, v in b_info.items()}
        else:
            bm_w = getattr(b_info, 'width_mm', getattr(b_info, 'width', 230))
            bm_d = getattr(b_info, 'depth_mm', getattr(b_info, 'depth', 400))
            bm_span = getattr(b_info, 'span_m', getattr(b_info, 'span', 4.0))
            bm_vol = (bm_w / 1000.0) * (bm_d / 1000.0) * bm_span
            bm_steel = bm_vol * 120.0
            row = {
                "Beam ID": str(bid),
                "Size (mm)": f"{bm_w:.0f}x{bm_d:.0f}",
                "Span (m)": f"{bm_span:.2f}",
                "Conc (m³)": f"{bm_vol:.2f}",
                "Steel (kg)": f"{bm_steel:.1f}",
                "Bot Steel": str(getattr(b_info,'bottom_bars_desc',getattr(b_info,'bottom_steel','N/A'))),
                "Top Steel": str(getattr(b_info,'top_bars_desc',getattr(b_info,'top_steel','N/A'))),
                "Stirrups": str(getattr(b_info,'stirrups_desc',getattr(b_info,'stirrups','N/A'))),
                "Status": str(getattr(b_info,'status','OK')),
            }
        beam_data.append(row)
else:
    for b in beams:
        span = math.hypot(
            b.end_point.x - b.start_point.x,
            b.end_point.y - b.start_point.y
        ) / 1000.0 if hasattr(b,'start_point') else 0
        w_mm = b.properties.width_mm if hasattr(b,'properties') else 230
        d_mm = b.properties.depth_mm if hasattr(b,'properties') else 400
        bm_vol = (w_mm / 1000.0) * (d_mm / 1000.0) * span
        bm_steel = bm_vol * 120.0
        beam_data.append({
            "Beam ID": str(b.id),
            "Span (m)": f"{span:.2f}",
            "Size (mm)": f"{w_mm:.0f}x{d_mm:.0f}",
            "Conc (m³)": f"{bm_vol:.2f}",
            "Steel (kg)": f"{bm_steel:.1f}",
            "Bot Steel": "N/A",
            "Top Steel": "N/A",
            "Stirrups": "N/A",
            "Status": "N/A",
        })
if beam_data:
    st.dataframe(pd.DataFrame(beam_data), use_container_width=True, hide_index=True)
else:
    st.info("No beams available.")

st.divider()

# 4. Slab Schedule
st.markdown("## Slab Schedule")
slab_data = []
if hasattr(gm, 'slab_schedule') and gm.slab_schedule:
    for sid, s_info in gm.slab_schedule.items():
        thk = getattr(s_info, 'thickness_mm', getattr(s_info, 'thickness', 125))
        area = getattr(s_info, 'area_m2', getattr(s_info, 'area', 16.0))
        s_vol = area * (thk / 1000.0)
        s_steel = s_vol * 90.0
        slab_data.append({
            "Slab ID": str(sid),
            "Thickness (mm)": f"{thk:.0f}",
            "Area (m²)": f"{area:.2f}",
            "Conc (m³)": f"{s_vol:.2f}",
            "Steel (kg)": f"{s_steel:.1f}",
            "Main Steel": str(getattr(s_info, 'main_steel_desc', getattr(s_info, 'main_steel', 'T8@150'))),
            "Distribution": str(getattr(s_info, 'dist_steel_desc', getattr(s_info, 'dist_steel', 'T8@175'))),
        })

if slab_data:
    st.dataframe(pd.DataFrame(slab_data), use_container_width=True, hide_index=True)
else:
    st.info("No slab schedule available.")

st.divider()

# 5. Footing Schedule
st.markdown("## Footing Schedule")
footing_data = []
footings_list = st.session_state.get('footings', [])
for i, cid in enumerate(level_0_cols):
    c_id = getattr(cid, 'id', str(cid))
    if i < len(footings_list):
        f = footings_list[i]
        try:
            ft_vol = getattr(f, 'concrete_vol_m3', f.length_m * f.width_m * (f.thickness_mm / 1000.0))
            ft_steel = ft_vol * 80.0
            footing_data.append({
                "Column ID": c_id,
                "Footing Size (m)": f"{f.length_m:.1f}x{f.width_m:.1f}",
                "Depth (m)": f"{f.thickness_mm/1000:.2f}",
                "Conc (m³)": f"{ft_vol:.2f}",
                "Steel (kg)": f"{ft_steel:.1f}",
                "Punching Shear": getattr(f, 'punching_shear_status', 'OK'),
                "One-Way Shear": getattr(f, 'one_way_shear_ok', True),
                "Bending OK": getattr(f, 'bending_ok', True),
            })
        except AttributeError:
            footing_data.append({"Column ID": c_id, "Details": str(f)})

if footing_data:
    st.dataframe(pd.DataFrame(footing_data), use_container_width=True, hide_index=True)
else:
    st.info("No footings available.")

st.divider()

# 6. Math Inspector
st.markdown("## Math Inspector")
if hasattr(gm, 'rebar_schedule') and gm.rebar_schedule:
    col_ids = list(gm.rebar_schedule.keys())
    selected_col = st.selectbox("Select Column for Math Log", ["None"] + col_ids)
    if selected_col != "None":
        log = getattr(gm.rebar_schedule[selected_col], 'math_log', "No math log available.")
        st.code(log, language="text")
else:
    st.info("Math Inspector requires rebar schedule data.")

st.divider()

# 7. Wall Schedule & Masonry Takeoff
st.markdown("## 🧱 Wall Schedule & Masonry Takeoff")
st.caption("Quantities calculated per IS 1077 (Clay Bricks), IS 2250 (Mortar Mixes), IS 1200 (Opening Deductions), and IS 1661 / IS 2402 (Plastering).")

wall_bom = st.session_state.get('wall_bom')
if not wall_bom and gm and hasattr(gm, 'walls') and gm.walls:
    from src.wall_calculator import WallCalculator
    m_ratio = st.session_state.get('mortar_ratio', 4)
    w_op = st.session_state.get('wall_opening_fraction', 0.33)
    wall_calc = WallCalculator(mortar_ratio=m_ratio, wc_ratio=0.50, opening_fraction=w_op)
    wall_bom = wall_calc.calculate_all(
        gm.walls,
        num_stories=getattr(gm, 'num_stories', 1),
        floor_height_m=getattr(gm, 'story_height_m', 3.5),
        slab_thickness_mm=125.0,
        beam_depth_mm=400.0,
    )
    st.session_state['wall_bom'] = wall_bom

if wall_bom:
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
        "📋 Wall Sections", 
        "🧱 Brickwork Takeoff", 
        "🎨 Plastering Takeoff", 
        "🖌️ Paint & Finishes", 
        "📐 Formula Reference"
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
            st.dataframe(df_walls, use_container_width=True, hide_index=True)
            csv_data = df_walls.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Complete Wall Takeoff (CSV)",
                data=csv_data,
                file_name="Wall_Takeoff_Schedule.csv",
                mime="text/csv",
                key="download_wall_takeoff_csv"
            )

        st.markdown("#### 🔍 Section Inspector")
        sel_wall_id = st.selectbox("Select Wall Section to Inspect", [s.wall_id for s in wb.wall_sections], key="select_inspect_wall")
        sel_sec = next((s for s in wb.wall_sections if s.wall_id == sel_wall_id), None)
        if sel_sec:
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.markdown("**📐 Geometry**")
                st.write(f"• Span: {sel_sec.col_start} → {sel_sec.col_end}")
                st.write(f"• Type: {'Exterior (230mm)' if sel_sec.is_exterior else 'Interior (115mm)'}")
                st.write(f"• Length: {sel_sec.length_m:.2f} m")
                st.write(f"• Clear Height: {sel_sec.clear_height_m:.2f} m")
                st.write(f"• Thickness: {int(sel_sec.core_thickness_m*1000)} mm")
                st.write(f"• Gross Vol: {sel_sec.wall_volume_m3:.3f} m³")
            with sc2:
                st.markdown("**🧱 Brickwork Takeoff**")
                st.write(f"• Bricks (per floor): {sel_sec.num_bricks} Nos")
                st.write(f"• Bricks (building total): {sel_sec.num_bricks * num_stories} Nos")
                st.write(f"• Solid Brick Vol: {sel_sec.total_brick_vol_m3:.3f} m³")
                st.write(f"• Wet Mortar: {sel_sec.wet_mortar_vol_m3:.3f} m³")
                st.write(f"• Dry Mortar: {sel_sec.dry_mortar_vol_m3:.3f} m³")
            with sc3:
                st.markdown("**🧪 Mortar & Plaster Materials**")
                st.write(f"• Mortar Cement: {sel_sec.mortar_cement_kg:.1f} kg ({sel_sec.mortar_cement_bags} bags)")
                st.write(f"• Mortar Sand: {sel_sec.mortar_sand_tonnes:.3f} T")
                st.write(f"• Mortar Water: {sel_sec.mortar_water_litres:.1f} L")
                st.write(f"• Plaster Area: {sel_sec.plaster_area_m2:.1f} m²")
                st.write(f"• Plaster Cement: {sel_sec.plaster_cement_kg:.1f} kg ({sel_sec.plaster_cement_bags} bags)")
                st.write(f"• Plaster Sand: {sel_sec.plaster_sand_tonnes:.3f} T")
            with sc4:
                st.markdown("**🎨 Surface Coatings & Paint**")
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
        st.dataframe(pd.DataFrame(m_data), use_container_width=True, hide_index=True)

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
        st.dataframe(pd.DataFrame(p_data), use_container_width=True, hide_index=True)

    with w_tab4:
        st.markdown("### Paint & Architectural Surface Coatings")
        paint_data = [
            {"Coating Layer": "Primer (Internal & External)", "Coats": f"{1} coat", "Film Thickness": "25–40 microns", "Coverage": "8 m²/Litre", "Total Required": f"{wb.total_primer_litres:.1f} Litres"},
            {"Coating Layer": "Wall Putty (Internal Faces)", "Coats": f"{2} coats", "Layer Thickness": "1–2 mm total", "Consumption": "1.5 kg/m²", "Total Required": f"{wb.total_putty_kg:,.1f} kg"},
            {"Coating Layer": "Interior Acrylic Emulsion", "Coats": f"{2} coats", "Film Thickness": "30–40 microns/coat", "Coverage": "12 m²/Litre", "Total Required": f"{wb.total_emulsion_int_litres:.1f} Litres"},
            {"Coating Layer": "Exterior Weather-Proof Emulsion", "Coats": f"{2} coats", "Film Thickness": "40–60 microns/coat", "Coverage": "10 m²/Litre", "Total Required": f"{wb.total_emulsion_ext_litres:.1f} Litres"},
        ]
        st.dataframe(pd.DataFrame(paint_data), use_container_width=True, hide_index=True)

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
else:
    st.info("Run analysis on the main Dashboard to generate wall design calculations.")

# Sidebar
with st.sidebar:
    render_is_code_reference()
