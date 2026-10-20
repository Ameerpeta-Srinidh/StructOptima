"""Drawings & 3D: the A3 site drawing set, the 3D model, plans and DXF exports."""
import datetime
import os
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from src.dxf_exporter import ProfessionalDXFExporter, StructuralDXFExporter
from src.ui_components import page_title, require_results
from src.visualizer import Visualizer

require_results()
S = st.session_state
res = S['design_results']
gm = res.gm
all_beams = S.get('all_beams') or S.get('beams', [])
footings = S.get('footings', [])
project_name = S.get('project_name', "PROPOSED BUILDING")
engineer_name = S.get('engineer_name', "STRUCTURAL ENGINEER")
num_stories = gm.num_stories
view_mode = S.get('in_view_mode', "Engineering")


def _dxf_bytes(write):
    """Run an exporter that writes to a path and return the file bytes. Exports never go to the working
    directory (finding N10)."""
    with tempfile.TemporaryDirectory(prefix="structoptima_dxf_") as d:
        path = os.path.join(d, "out.dxf")
        write(path)
        with open(path, "rb") as fh:
            return fh.read()


def _design_info():
    return {"project_name": project_name, "engineer": engineer_name,
            "date": datetime.datetime.now().strftime("%d-%m-%Y"), "sheet": "S-1", "scale": "1:100"}


page_title("Drawings & 3D", "Drawings are generated from the design. PRELIMINARY — NOT FOR CONSTRUCTION.")
view = st.radio("View", ["Drawing sheets", "3D model", "Plan", "CAD view", "DXF exports"], key="dwg_view",
                horizontal=True, label_visibility="collapsed")

if view == "Drawing sheets":
    from src.drawings import build_drawing_set, sheets_to_pdf, sheets_to_zip
    _project = {"project": project_name, "engineer": engineer_name, "ref": S.get('drawing_ref', ''),
                "date": datetime.date.today().isoformat(), "status_line": f"DESIGN STATUS: {res.status}"}
    _key = (id(res), tuple(sorted(_project.items())))
    if S.get('_drawing_set_key') != _key:
        S['_drawing_set'] = build_drawing_set(res.gm, res.beams, res.footings, _project)
        S['_drawing_set_key'] = _key
    _sheets = S['_drawing_set']
    if res.status != "PASS":
        st.warning(f"Design status {res.status}: members needing review are drawn in orange (WARN) / red (FAIL).")
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    _labels = [f"{s.number}  {s.title}" for s in _sheets]
    _sel = c1.selectbox("Sheet", range(len(_sheets)), format_func=lambda i: _labels[i], key="drawing_sheet_sel")
    with c2.popover("Download", icon=":material/download:", width="stretch"):
        st.download_button("Full set — PDF (A3)", lambda: sheets_to_pdf(_sheets), "StructOptima_Drawings.pdf",
                           "application/pdf", key="dl_dwg_pdf", icon=":material/picture_as_pdf:", width="stretch")
        st.download_button(f"{_sheets[_sel].number} — DXF", lambda: _sheets[_sel].drawing.to_dxf_bytes(),
                           f"{_sheets[_sel].number}.dxf", "application/dxf", key="dl_dwg_dxf", width="stretch")
        st.download_button("All sheets — ZIP (PDF + DXF + SVG)", lambda: sheets_to_zip(_sheets),
                           "StructOptima_Drawings.zip", "application/zip", key="dl_dwg_zip", width="stretch")
        try:
            from src.ifc_exporter import export_ifc
            st.download_button("BIM model — IFC4", lambda: export_ifc(res.gm, res.beams, res.footings, project_name),
                               "StructOptima_Model.ifc", "application/x-step", key="dl_ifc", width="stretch")
        except ImportError:
            st.caption("IFC export needs `ifcopenshell`.")
    _svg = _sheets[_sel].drawing.to_svg()
    components.html(f"""
    <div id="wrap" style="width:100%;height:700px;overflow:hidden;border:1px solid #E4E7EC;border-radius:8px;
         background:#F8FAFC;cursor:grab;position:relative">
      <div id="pz" style="transform-origin:0 0;width:100%;height:100%">{_svg.replace('width="420.0mm" height="297.0mm"', 'width="100%" height="100%"')}</div>
      <div style="position:absolute;right:8px;top:6px;font:12px Inter,sans-serif;color:#475467;background:#fff;
           padding:2px 8px;border-radius:4px;border:1px solid #E4E7EC">Scroll or pinch to zoom · drag to pan ·
           double-click to reset</div>
    </div>
    <script>
      const w=document.getElementById('wrap'), p=document.getElementById('pz');
      let s=1,x=0,y=0,drag=false,sx=0,sy=0,pinch=null;
      const ap=()=>{{p.style.transform=`translate(${{x}}px,${{y}}px) scale(${{s}})`;}};
      const zoomAt=(mx,my,k)=>{{const ns=Math.min(12,Math.max(0.5,s*k));x=mx-(mx-x)*ns/s;y=my-(my-y)*ns/s;s=ns;ap();}};
      w.addEventListener('wheel',e=>{{e.preventDefault();const r=w.getBoundingClientRect();
        zoomAt(e.clientX-r.left,e.clientY-r.top,e.deltaY<0?1.15:1/1.15);}},{{passive:false}});
      w.addEventListener('mousedown',e=>{{drag=true;sx=e.clientX-x;sy=e.clientY-y;w.style.cursor='grabbing';}});
      window.addEventListener('mouseup',()=>{{drag=false;w.style.cursor='grab';}});
      window.addEventListener('mousemove',e=>{{if(drag){{x=e.clientX-sx;y=e.clientY-sy;ap();}}}});
      w.addEventListener('dblclick',()=>{{s=1;x=0;y=0;ap();}});
      const dist=t=>Math.hypot(t[0].clientX-t[1].clientX,t[0].clientY-t[1].clientY);
      w.addEventListener('touchstart',e=>{{if(e.touches.length===2){{pinch=dist(e.touches);}}
        else{{drag=true;sx=e.touches[0].clientX-x;sy=e.touches[0].clientY-y;}}}},{{passive:true}});
      w.addEventListener('touchmove',e=>{{e.preventDefault();const r=w.getBoundingClientRect();
        if(e.touches.length===2&&pinch){{const d=dist(e.touches);
          zoomAt((e.touches[0].clientX+e.touches[1].clientX)/2-r.left,(e.touches[0].clientY+e.touches[1].clientY)/2-r.top,d/pinch);pinch=d;}}
        else if(drag){{x=e.touches[0].clientX-sx;y=e.touches[0].clientY-sy;ap();}}}},{{passive:false}});
      w.addEventListener('touchend',()=>{{drag=false;pinch=null;}});
    </script>""", height=710)
    st.caption("Sheets: S-01 columns · S-02 footings · S-03 beams & slabs · S-04 sections · S-05 slab reinforcement · "
               "S-06 footing sections (+ A/B continuation sheets). Marks match the Members page. DXF sheets are in "
               "paper millimetres (plot 1:1).")

elif view == "3D model":
    from src.viewer_model import build_scene, bundle_available, viewer_html
    if bundle_available():
        st.caption("Orbit the building, isolate a storey, cut a section, colour by design status, click any member for "
                   "its size, bars and status, or switch View → Walk-through to walk the floors (keyboard, mouse or the "
                   "on-screen buttons on a tablet / phone).")
        if S.get('_viewer_key') != id(res):
            S['_viewer_html'] = viewer_html(build_scene(res.gm, res.beams, res.footings), 700)
            S['_viewer_key'] = id(res)
        components.html(S['_viewer_html'], height=720)
    else:
        st.info("The 3D viewer bundle (components/viewer3d/dist/viewer.js) is missing.")
    if st.toggle("Show the older 3D model view (needs internet: loads model-viewer from Google)", key="legacy_3d"):
        show_walls = st.toggle("Show walls", value=S.get('in_show_walls', True), key="toggle_show_3d_walls")
        try:
            from src.geometry_exporter import GeometryExporter
            scene = GeometryExporter.create_structure_scene(grid_mgr=gm, beams=all_beams, footings=footings,
                                                            view_mode=view_mode, arch_walls=S.get('arch_walls'),
                                                            show_walls=show_walls)
            glb_data = GeometryExporter.export_to_glb_base64(scene)
            components.html(f"""
            <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.1.1/model-viewer.min.js"></script>
            <style>model-viewer {{width:100%;height:600px;background-color:#f5f5f5;border-radius:8px;}}</style>
            <model-viewer src="{glb_data}" camera-controls auto-rotate shadow-intensity="1" exposure="1.0"
              interaction-prompt="auto" camera-orbit="-45deg 55deg 20m"></model-viewer>""", height=620)
        except Exception as _e:
            st.error(f"Unable to render the older 3D view: {_e}")

elif view == "Plan":
    level_sel = st.slider("Level", 1, max(1, num_stories), 1, key="plan_level") if num_stories > 1 else 1
    st.plotly_chart(Visualizer().create_2d_plan(gm, all_beams, view_mode=view_mode, level=level_sel), key="plan_2d")

elif view == "CAD view":
    st.caption("Structural plan rendered from the DXF export. Scroll to zoom, drag to pan.")
    from src.svg_viewer import get_interactive_svg_html
    with tempfile.TemporaryDirectory(prefix="structoptima_dxf_") as d:
        temp_dxf = os.path.join(d, "viewer.dxf")
        StructuralDXFExporter.export_structural_dxf(gm, all_beams, temp_dxf)
        components.html(get_interactive_svg_html(temp_dxf, height=640), height=660)

else:
    st.caption("Plan exports for CAD. Files are generated when you click.")
    with st.container(horizontal=True):
        st.download_button("Structural plan", lambda: _dxf_bytes(
            lambda p: StructuralDXFExporter.export_structural_dxf(gm, all_beams, p)),
            "Structural_Plan.dxf", "application/dxf", key="dl_struct_dxf", icon=":material/download:")
        st.download_button("Foundation plan", lambda: _dxf_bytes(
            lambda p: ProfessionalDXFExporter(gm, all_beams, _design_info(), drawing_type="FOUNDATION").export(p)),
            "Foundation_Plan_Professional.dxf", "application/dxf", key="dl_found_dxf", icon=":material/download:")
        st.download_button("Beam schedule", lambda: _dxf_bytes(
            lambda p: ProfessionalDXFExporter(gm, all_beams, _design_info(),
                                              drawing_type="FOUNDATION").export_beam_schedule_table(p)),
            "Beam_Schedule.dxf", "application/dxf", key="dl_beam_dxf", icon=":material/download:")
    st.markdown("**Floor plans**")
    with st.container(horizontal=True):
        for lvl in range(num_stories):
            st.download_button(f"Floor {lvl}", lambda lvl=lvl: _dxf_bytes(
                lambda p: StructuralDXFExporter.export_floor_dxf(gm, all_beams, lvl, p)),
                f"Floor_{lvl}_Plan.dxf", "application/dxf", key=f"dxf_floor_{lvl}", icon=":material/download:")
