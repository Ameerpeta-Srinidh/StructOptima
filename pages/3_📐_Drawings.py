import streamlit as st
import streamlit.components.v1 as components
import sys, os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.ui_components import inject_css, render_project_header, render_no_analysis_warning, render_is_code_reference
from src.geometry_exporter import GeometryExporter
from src.visualizer import Visualizer
from src.dxf_exporter import StructuralDXFExporter, ProfessionalDXFExporter
import datetime

st.set_page_config(page_title='StructOptima — Drawings', layout='wide', page_icon='📐')
inject_css()
render_project_header()
render_is_code_reference()

if not st.session_state.get('analysis_done'):
    render_no_analysis_warning()
    st.stop()

# Get required data from session state
gm = st.session_state.get('gm')
all_beams = st.session_state.get('beams') # or we generate all_beams like in app.py? Wait, in app.py 'all_beams' was constructed inside the run logic. We should reconstruct or get it from session state.

# If all_beams isn't in session state, we might need to recreate it. Wait, the prompt says "Get gm, all_beams, footings from session state." Let's just fetch them.
all_beams = st.session_state.get('all_beams', st.session_state.get('beams', []))
footings = st.session_state.get('footings', [])
project_name = st.session_state.get('project_name', "PROPOSED BUILDING")
engineer_name = st.session_state.get('engineer_name', "STRUCTURAL ENGINEER")
num_stories = gm.num_stories if gm else 1
v_mode_str = st.session_state.get('view_mode', "Engineering")

v_tab1, v_tab2 = st.tabs(["3D View", "2D Plan View"])

with v_tab1:
    st.markdown("### Engineering 3D Viewer (Mobile & AR Ready)")
    if gm and all_beams:
        scene = GeometryExporter.create_structure_scene(
            grid_mgr=gm, 
            beams=all_beams, 
            footings=footings, 
            view_mode=v_mode_str,
            arch_walls=st.session_state.get('arch_walls')
        )
        glb_data = GeometryExporter.export_to_glb_base64(scene)
        
        # Build the HTML for model-viewer
        html_code = f"""
        <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.1.1/model-viewer.min.js"></script>
        <style>
          model-viewer {{
            width: 100%;
            height: 600px;
            background-color: #f5f5f5;
            border-radius: 8px;
          }}
        </style>
        <model-viewer 
          src="{glb_data}" 
          camera-controls 
          auto-rotate 
          ar
          shadow-intensity="1"
          exposure="1.0"
          interaction-prompt="auto"
          camera-orbit="-45deg 55deg 20m"
        >
        </model-viewer>
        """
        components.html(html_code, height=620)

with v_tab2:
    if gm and all_beams:
        viz = Visualizer()
        level_sel = st.slider("Select Level", 1, max(1, num_stories), 1)
        fig_2d = viz.create_2d_plan(gm, all_beams, view_mode=v_mode_str, level=level_sel)
        st.plotly_chart(fig_2d, use_container_width=True)

st.markdown("---")
st.subheader("DXF Downloads")

c_d1, c_d2 = st.columns(2)

if gm and all_beams:
    # Structural DXF Export
    dxf_filename = "Structural_Plan.dxf"
    StructuralDXFExporter.export_structural_dxf(gm, all_beams, dxf_filename)
    
    with open(dxf_filename, "rb") as f:
        c_d1.download_button(
            label="📐 Download Structural Plan (.dxf)",
            data=f.read(),
            file_name="Structural_Plan.dxf",
            mime="application/dxf"
        )

    # Professional DXF Export (Foundation Plan & Beam Schedule)
    prof_dxf_filename = "Foundation_Plan_Professional.dxf"
    design_info = {
        "project_name": project_name,
        "engineer": engineer_name,
        "date": datetime.datetime.now().strftime("%d-%m-%Y"),
        "sheet": "S-1",
        "scale": "1:100"
    }
    
    try:
        prof_exporter = ProfessionalDXFExporter(gm, all_beams, design_info, drawing_type="FOUNDATION")
        prof_exporter.export(prof_dxf_filename)
        with open(prof_dxf_filename, "rb") as f:
            c_d2.download_button(
                label="🏗️ Prof. Foundation Plan (.dxf)",
                data=f.read(),
                file_name="Foundation_Plan_Professional.dxf",
                mime="application/dxf"
            )
            
        beam_sched_filename = "Beam_Schedule.dxf"
        prof_exporter.export_beam_schedule_table(beam_sched_filename)
        with open(beam_sched_filename, "rb") as f:
            c_d2.download_button(
                label="📋 Download Beam Schedule (.dxf)",
                data=f.read(),
                file_name="Beam_Schedule.dxf",
                mime="application/dxf"
            )
    except Exception as e:
        c_d2.error(f"Prof. DXF export failed: {e}")
    
    # Layer-wise Exports Section
    st.markdown("---")
    st.markdown("#### 📐 Layer-wise Structural Plans")
    
    floor_cols = st.columns(min(num_stories, 4))
    for lvl in range(num_stories):
        col_idx = lvl % 4
        
        # Generate floor DXF
        floor_dxf = f"Floor_{lvl}_Plan.dxf"
        StructuralDXFExporter.export_floor_dxf(gm, all_beams, lvl, floor_dxf)
        
        with open(floor_dxf, "rb") as f:
            floor_cols[col_idx].download_button(
                label=f"📐 Floor {lvl} DXF",
                data=f.read(),
                file_name=f"Floor_{lvl}_Plan.dxf",
                mime="application/dxf",
                key=f"dxf_floor_{lvl}"
            )
