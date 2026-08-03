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
cols_list = []
for level in sorted(gm.levels.keys()):
    for col in gm.levels[level].columns:
        cols_list.append((level, col))

all_levels = sorted(list(set(level for level, _ in cols_list)))
if all_levels:
    col1, col2 = st.columns(2)
    with col1:
        selected_level = st.selectbox("Select Level", ["All"] + [str(l) for l in all_levels])
    with col2:
        status_filter = st.selectbox("Status Filter", ["All", "Pass", "Warning", "Fail"])

    level_groups = all_levels if selected_level == "All" else [int(selected_level)]

    for level in level_groups:
        render_section_header(f'Level {level} (Floor {level})')
        level_cols = [c for l, c in cols_list if l == level]
        
        data = []
        for col in level_cols:
            load = getattr(col, 'load_kn', 0)
            width = getattr(col, 'width_nb', 300)
            depth = getattr(col, 'depth_nb', 450)
            capacity = getattr(col, 'capacity', 0)
            
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

            footing_size = "N/A"
            if level == min(all_levels) and col.id in footings:
                f = footings[col.id]
                footing_size = f"{f.L:.1f}x{f.B:.1f}x{f.D:.2f}m"

            main_steel = "N/A"
            stirrups = "N/A"
            if hasattr(gm, 'rebar_schedule') and col.id in gm.rebar_schedule:
                rebar = gm.rebar_schedule[col.id]
                main_steel = getattr(rebar, 'main_steel', "N/A")
                stirrups = getattr(rebar, 'stirrups', "N/A")

            data.append({
                "ID": col.id,
                "Size (mm)": f"{width}x{depth}",
                "Load (kN)": f"{load:.1f}",
                "D/C Ratio": dc,
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
        beam_data.append(b_info)
else:
    for b in beams:
        beam_data.append({
            "Beam ID": b.id,
            "Span (m)": f"{getattr(b, 'span', 0):.2f}",
            "Size (mm)": f"{getattr(b, 'width', 0)}x{getattr(b, 'depth', 0)}",
            "Bottom Steel": "N/A",
            "Stirrups": "N/A",
            "Status": "N/A"
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
        slab_data.append(s_info)

if slab_data:
    st.dataframe(pd.DataFrame(slab_data), use_container_width=True, hide_index=True)
else:
    st.info("No slab schedule available.")

st.divider()

# 5. Footing Schedule
st.markdown("## Footing Schedule")
footing_data = []
for cid in level_0_cols:
    c_id = getattr(cid, 'id', cid)
    if c_id in footings:
        f = footings[c_id]
        footing_data.append({
            "Column ID": c_id,
            "Footing Size (m)": f"{f.L:.1f}x{f.B:.1f}",
            "Depth (m)": f"{f.D:.2f}",
            "Punching Shear Status": getattr(f, 'punching_shear_status', 'N/A')
        })

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

# Sidebar
with st.sidebar:
    render_is_code_reference()
