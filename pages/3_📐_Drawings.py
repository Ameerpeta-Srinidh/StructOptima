import streamlit as st
import streamlit.components.v1 as components
import sys, os

sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.ui_components import inject_css, render_project_header, render_no_analysis_warning, render_is_code_reference
from src.geometry_exporter import GeometryExporter
from src.visualizer import Visualizer
from src.dxf_exporter import StructuralDXFExporter, ProfessionalDXFExporter
import datetime
import tempfile

# Exports are written to a private temporary directory, never to the current
# working directory (writing there overwrote tracked repository files - finding N10).
_EXPORT_DIR = tempfile.mkdtemp(prefix="structoptima_dxf_")

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

v_tab0, v_tab1, v_tab2, v_tab3 = st.tabs(["🗂️ Site Drawings (A3 set)", "3D View", "2D Plan View", "Interactive CAD"])

with v_tab0:
    _res = st.session_state.get('design_results')
    if _res is None:
        st.info("Run the analysis to generate the drawing set.")
    else:
        from src.drawings import build_drawing_set, sheets_to_pdf, sheets_to_zip

        _project = {
            "project": project_name,
            "engineer": engineer_name,
            "ref": st.session_state.get('drawing_ref', ''),
            "date": datetime.date.today().isoformat(),
            "status_line": f"DESIGN STATUS: {_res.status}",
        }
        _key = (id(_res), tuple(sorted(_project.items())))
        if st.session_state.get('_drawing_set_key') != _key:
            st.session_state['_drawing_set'] = build_drawing_set(_res.gm, _res.beams, _res.footings, _project)
            st.session_state['_drawing_set_key'] = _key
        _sheets = st.session_state['_drawing_set']

        if _res.status != "PASS":
            st.warning(f"Design status {_res.status}: members needing review are drawn in orange (WARN) / red (FAIL). "
                       "Drawings are PRELIMINARY - NOT FOR CONSTRUCTION.")
        _labels = [f"{s.number}  {s.title}" for s in _sheets]
        _sel = st.selectbox("Sheet", range(len(_sheets)), format_func=lambda i: _labels[i], key="drawing_sheet_sel")
        _svg = _sheets[_sel].drawing.to_svg()
        components.html(f"""
        <div id="wrap" style="width:100%;height:680px;overflow:hidden;border:1px solid #CBD5E1;border-radius:6px;
             background:#F8FAFC;cursor:grab;position:relative">
          <div id="pz" style="transform-origin:0 0;width:100%">{_svg.replace('width="420.0mm" height="297.0mm"', 'width="100%"')}</div>
          <div style="position:absolute;right:8px;top:6px;font:12px sans-serif;color:#475569;background:#fff;
               padding:2px 6px;border-radius:4px">Scroll to zoom · drag to pan · double-click to reset</div>
        </div>
        <script>
          const w=document.getElementById('wrap'), p=document.getElementById('pz');
          let s=1,x=0,y=0,drag=false,sx=0,sy=0;
          const ap=()=>{{p.style.transform=`translate(${{x}}px,${{y}}px) scale(${{s}})`;}};
          w.addEventListener('wheel',e=>{{e.preventDefault();const r=w.getBoundingClientRect();
            const mx=e.clientX-r.left,my=e.clientY-r.top,k=e.deltaY<0?1.15:1/1.15;
            const ns=Math.min(12,Math.max(0.5,s*k));x=mx-(mx-x)*ns/s;y=my-(my-y)*ns/s;s=ns;ap();}},{{passive:false}});
          w.addEventListener('mousedown',e=>{{drag=true;sx=e.clientX-x;sy=e.clientY-y;w.style.cursor='grabbing';}});
          window.addEventListener('mouseup',()=>{{drag=false;w.style.cursor='grab';}});
          window.addEventListener('mousemove',e=>{{if(drag){{x=e.clientX-sx;y=e.clientY-sy;ap();}}}});
          w.addEventListener('dblclick',()=>{{s=1;x=0;y=0;ap();}});
        </script>""", height=700)

        _d1, _d2, _d3 = st.columns(3)
        _d1.download_button("📕 Full drawing set (PDF, A3)", sheets_to_pdf(_sheets), "StructOptima_Drawings.pdf",
                            "application/pdf", key="dl_dwg_pdf")
        _d2.download_button(f"📐 {_sheets[_sel].number} (DXF)", _sheets[_sel].drawing.to_dxf_bytes(),
                            f"{_sheets[_sel].number}.dxf", "application/dxf", key="dl_dwg_dxf")
        _d3.download_button("🗜️ All sheets (ZIP: PDF + DXF + SVG)", sheets_to_zip(_sheets), "StructOptima_Drawings.zip",
                            "application/zip", key="dl_dwg_zip")
        try:
            from src.ifc_exporter import export_ifc
            if st.session_state.get('_ifc_key') != _key:
                st.session_state['_ifc_bytes'] = export_ifc(_res.gm, _res.beams, _res.footings, project_name)
                st.session_state['_ifc_key'] = _key
            st.download_button("🧊 BIM model (IFC4) — open in any IFC viewer", st.session_state['_ifc_bytes'],
                               "StructOptima_Model.ifc", "application/x-step", key="dl_ifc")
        except ImportError:
            st.caption("IFC export needs `ifcopenshell` (pip install ifcopenshell).")
        st.caption("Sheets: S-01 columns · S-02 footings · S-03 beams & slabs · S-04 sections · S-05 slab "
                   "reinforcement · S-06 footing sections (+ A/B continuation sheets). Marks (C1, B1, F1, S1) match "
                   "the Schedules page. DXF sheets are in paper millimetres (plot 1:1).")

with v_tab1:
    _res3d = st.session_state.get('design_results')
    from src.viewer_model import bundle_available, build_scene, viewer_html
    if _res3d is not None and bundle_available():
        st.caption("Orbit the designed building, isolate a storey, cut a section, colour by design status, click any "
                   "member for its size, bars and status, or switch View → Walk-through to walk the floors "
                   "(keyboard, mouse or the on-screen buttons on a tablet / phone).")
        _skey = id(_res3d)
        if st.session_state.get('_viewer_key') != _skey:
            st.session_state['_viewer_html'] = viewer_html(build_scene(_res3d.gm, _res3d.beams, _res3d.footings), 660)
            st.session_state['_viewer_key'] = _skey
        components.html(st.session_state['_viewer_html'], height=680)
        _show_legacy_3d = st.checkbox("Show the older 3D model view", value=False, key="legacy_3d")
    else:
        _show_legacy_3d = True
    if gm and all_beams and _show_legacy_3d:
        col_w_tgl, col_w_info = st.columns([1, 3])
        with col_w_tgl:
            show_walls = st.checkbox("🧱 Show Walls", value=st.session_state.get('show_3d_walls', True), key="toggle_show_3d_walls")
        with col_w_info:
            st.caption("Toggle walls ON/OFF to inspect structural RC frame (columns & beams) or full architectural wall layout.")

        try:
            import importlib
            import src.geometry_exporter as _ge_mod
            importlib.reload(_ge_mod)
            _GeometryExporter = _ge_mod.GeometryExporter

            scene = _GeometryExporter.create_structure_scene(
                grid_mgr=gm, 
                beams=all_beams, 
                footings=footings, 
                view_mode=v_mode_str,
                arch_walls=st.session_state.get('arch_walls'),
                show_walls=show_walls
            )
            glb_data = _GeometryExporter.export_to_glb_base64(scene)
        except Exception as _e:
            st.error(f"⚠️ Unable to render 3D model: {_e}")
            glb_data = ""
        
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

with v_tab3:
    st.markdown("### Interactive Structural CAD")
    st.info("💡 **Tip:** Scroll to zoom, click and drag to pan.")
    if gm and all_beams:
        # Generate temporary DXF for the viewer
        temp_dxf = os.path.join(_EXPORT_DIR, "temp_viewer.dxf")
        StructuralDXFExporter.export_structural_dxf(gm, all_beams, temp_dxf)
        
        # Convert to SVG HTML
        from src.svg_viewer import get_interactive_svg_html
        svg_html = get_interactive_svg_html(temp_dxf, height=600)
        
        # Render in Streamlit
        components.html(svg_html, height=620)
        
        import os
        if os.path.exists(temp_dxf):
            os.remove(temp_dxf)

st.markdown("---")
st.subheader("DXF Downloads")

c_d1, c_d2 = st.columns(2)

if gm and all_beams:
    # Structural DXF Export
    dxf_filename = os.path.join(_EXPORT_DIR, "Structural_Plan.dxf")
    StructuralDXFExporter.export_structural_dxf(gm, all_beams, dxf_filename)
    
    with open(dxf_filename, "rb") as f:
        c_d1.download_button(
            label="📐 Download Structural Plan (.dxf)",
            data=f.read(),
            file_name="Structural_Plan.dxf",
            mime="application/dxf"
        )

    # Professional DXF Export (Foundation Plan & Beam Schedule)
    prof_dxf_filename = os.path.join(_EXPORT_DIR, "Foundation_Plan_Professional.dxf")
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
            
        beam_sched_filename = os.path.join(_EXPORT_DIR, "Beam_Schedule.dxf")
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
    
    floor_cols = st.columns(min(num_stories, 4))
    for lvl in range(num_stories):
        col_idx = lvl % 4
        
        # Generate floor DXF
        floor_dxf = os.path.join(_EXPORT_DIR, f"Floor_{lvl}_Plan.dxf")
        StructuralDXFExporter.export_floor_dxf(gm, all_beams, lvl, floor_dxf)
        
        with open(floor_dxf, "rb") as f:
            floor_cols[col_idx].download_button(
                label=f"📐 Floor {lvl} DXF",
                data=f.read(),
                file_name=f"Floor_{lvl}_Plan.dxf",
                mime="application/dxf",
                key=f"dxf_floor_{lvl}"
            )
