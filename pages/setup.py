"""Setup: project inputs and the design run."""
import streamlit as st

from src import ui_state
from src.building_types import BUILDING_TYPES, get_load_parameters
from src.grid_manager import GridManager
from src.logging_config import get_logger
from src.monitoring import capture_exception
from src.seismic import SEISMIC_ZONES, ZONE_DESCRIPTIONS
from src.ui_components import page_title, render_quick_reference, status_badge
from src.ui_tables import design_status_summary

logger = get_logger(__name__)
S = st.session_state
MODES = ui_state.MODES

page_title("Project setup", "Enter the building, site and design parameters, then run the design. "
                            "Nothing site-specific is assumed: the SBC and the site confirmation are required.")


def _store_upload(kind):
    f = S.get(f"upload_{kind}")
    if f is not None:
        S["model_file"] = {"name": f.name, "bytes": f.getvalue(), "kind": kind}
        S["in_layer_roles"] = None              # a new drawing starts from the suggestions
        ui_state.on_site_change()


def _plan_preview(width, length, cantilevers):
    """Column grid the design will start from (manual mode), drawn from the same GridManager the run uses."""
    import plotly.graph_objects as go
    gm = GridManager(width_m=width, length_m=length, num_stories=1, story_height_m=3.0)
    gm.cantilever_dirs = list(cantilevers)
    gm.cantilever_len_m = 1.5
    gm.generate_grid()
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=width, y1=length, line=dict(color="#98A2B3", width=1),
                  fillcolor="rgba(21,89,193,0.04)")
    cols = [c for c in gm.columns if c.level == 0]
    fig.add_trace(go.Scatter(x=[c.x for c in cols], y=[c.y for c in cols], mode="markers",
                             marker=dict(symbol="square", size=11, color="#1559C1"),
                             text=[c.id for c in cols], hovertemplate="%{text}<br>x %{x:.2f} m, y %{y:.2f} m<extra></extra>"))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, plot_bgcolor="white",
                      xaxis=dict(title="x (m)", showgrid=False, zeroline=False),
                      yaxis=dict(title="y (m)", showgrid=False, zeroline=False, scaleanchor="x"))
    st.plotly_chart(fig, config={"displayModeBar": False}, key="plan_preview")
    st.caption(f"Starting column grid: {len(cols)} columns. Column sizes and the final layout come from the design.")


def _set_roles(roles):
    S["in_layer_roles"] = roles
    S["layer_editor_version"] = S.get("layer_editor_version", 0) + 1


def _on_layer_edit(key, layers):
    from src.dxf_layers import ROLE_LABELS
    by_label = {v: k for k, v in ROLE_LABELS.items()}
    current = {r["Layer"]: by_label[r["Read as"]] for r in layers}
    for row, change in S[key].get("edited_rows", {}).items():
        if "Read as" in change:
            current[layers[int(row)]["Layer"]] = by_label[change["Read as"]]
    _set_roles(current)


def _dxf_reading(f):
    """How the drawing is read: one row per layer (the engineer can correct the role) and a plan preview of the
    columns, beams and walls the design will use."""
    import plotly.graph_objects as go
    from src.dxf_layers import ROLE_LABELS
    roles = S.get("in_layer_roles")
    data = ui_state.read_dxf_cached(f["bytes"], tuple(sorted(roles.items())) if roles is not None else None,
                                    bool(S["in_auto_frame"]))
    st.markdown("**How the drawing is read**")
    st.caption("Every office names layers differently, so each layer's role is suggested from its name and from what "
               "is drawn on it. Check the roles and the preview; change *Read as* where it is wrong. "
               "*Decide by shape*: closed column-sized outlines are columns, lines from column to column are beams, "
               "line pairs a wall thickness apart are walls.")
    layers = data["layers"]
    key = f"layer_editor_{S.get('layer_editor_version', 0)}"
    import pandas as pd
    st.data_editor(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in layers]),
                   key=key, hide_index=True, width="stretch", on_change=_on_layer_edit, args=(key, layers),
                   disabled=["Layer", "Holds", "Why", "Confidence"],
                   column_config={"Read as": st.column_config.SelectboxColumn(
                       "Read as", options=list(ROLE_LABELS.values()), required=True, width="medium"),
                       "Why": st.column_config.TextColumn("Why", width="large")})
    if roles is not None:
        st.button("Back to the suggested roles", on_click=_set_roles, args=(None,))
    if data["error"]:
        st.error(data["error"])
        return
    fig = go.Figure()
    for (x1, y1), (x2, y2) in data["walls"]:
        fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", line=dict(color="#C8CDD5", width=4),
                                 hoverinfo="skip", showlegend=False))
    for (x1, y1), (x2, y2) in data["beams"]:
        fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", line=dict(color="#E8833A", width=2),
                                 hoverinfo="skip", showlegend=False))
    for x, y, w, d, cid in data["columns"]:
        fig.add_shape(type="rect", x0=x - w / 2000, x1=x + w / 2000, y0=y - d / 2000, y1=y + d / 2000,
                      fillcolor="#1559C1", line=dict(width=0))
    fig.add_trace(go.Scatter(x=[c[0] for c in data["columns"]], y=[c[1] for c in data["columns"]], mode="markers",
                             marker=dict(size=6, color="#1559C1"), showlegend=False,
                             text=[f"{c[4]}: {c[2]:.0f} x {c[3]:.0f} mm as drawn" for c in data["columns"]],
                             hovertemplate="%{text}<br>x %{x:.2f} m, y %{y:.2f} m<extra></extra>"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      xaxis=dict(title="x (m)", showgrid=False, zeroline=False),
                      yaxis=dict(title="y (m)", showgrid=False, zeroline=False, scaleanchor="x"))
    st.plotly_chart(fig, config={"displayModeBar": False}, key="dxf_preview")
    st.caption(f"Read: **{len(data['columns'])} columns** (blue, as drawn), **{len(data['beams'])} beams** (orange), "
               f"**{len(data['walls'])} wall lines** (grey, under the beams where they coincide). The design may enlarge the columns; differences from the "
               f"drawing are listed in the results.")
    if data["warnings"]:
        with st.expander(f"{len(data['warnings'])} note(s) about the drawing", expanded=True):
            for w in data["warnings"]:
                st.markdown(f"- {w}")


left, right = st.columns([2.3, 1], gap="large")

with left:
    t_geo, t_loads, t_site, t_mat, t_mas = st.tabs(
        ["Building & geometry", "Occupancy & loads", "Site, seismic & wind", "Materials & modelling", "Masonry"])

    with t_geo:
        c1, c2, c3 = st.columns(3)
        c1.text_input("Project name", key="in_project_name")
        c2.text_input("Structural engineer", key="in_engineer", placeholder="Responsible engineer")
        c3.text_input("Drawing / job reference", key="in_drawing_ref")
        st.radio("Geometry source", MODES, key="in_mode", horizontal=True, on_change=ui_state.on_site_change,
                 help="Manual: rectangular plan with a regular column grid. DXF: architectural or structural "
                      "drawing. IFC: columns and beams from a BIM model.")
        mode = S["in_mode"]

        if mode == MODES[1]:
            st.file_uploader("DXF drawing", type=["dxf"], key="upload_dxf", on_change=_store_upload, args=("dxf",))
            f = ui_state.uploaded_file()
            if f:
                st.caption(f"Using **{f['name']}** ({len(f['bytes']) / 1024:.0f} kB). Upload another file to replace it.")
            st.toggle("Place columns automatically from the architecture", key="in_auto_frame",
                      help="Use when the drawing has walls only and no columns.")
            if f:
                try:
                    _dxf_reading(f)
                except Exception as e:  # preview only; the design run reports real errors
                    logger.error("DXF preview failed: %s", e)
                    capture_exception(e)
                    st.warning(f"The drawing preview could not be shown ({e}). The design run reports the details.")
        elif mode == MODES[2]:
            try:
                import ifcopenshell  # noqa: F401
                st.file_uploader("IFC model", type=["ifc"], key="upload_ifc", on_change=_store_upload, args=("ifc",))
                f = ui_state.uploaded_file()
                if f:
                    st.caption(f"Using **{f['name']}** ({len(f['bytes']) / 1024:.0f} kB).")
                st.info("IFC import reads IfcColumn / IfcBeam with rectangular profiles. Storeys and heights come "
                        "from the file.")
            except ImportError:
                st.error("IFC import needs the optional package `ifcopenshell` (pip install ifcopenshell).")

        g1, g2, g3, g4 = st.columns(4)
        if mode == MODES[0]:
            g1.number_input("Plan width (m)", 6.0, 50.0, step=0.5, key="in_width")
            g2.number_input("Plan length (m)", 6.0, 50.0, step=0.5, key="in_length")
        if mode != MODES[2]:
            g3.number_input("Storeys", 1, 50, step=1, key="in_stories")
            g4.number_input("Storey height (m)", 2.4, 6.0, step=0.1, key="in_story_h")
        if mode == MODES[0]:
            p1, p2 = st.columns([1, 1.3])
            with p1:
                st.pills("Cantilever balconies (1.5 m)", ui_state.CANTILEVER_SIDES, selection_mode="multi",
                         key="in_cantilevers", format_func=lambda s: {"top": "back", "bottom": "front"}.get(s, s))
                st.toggle("Staircase (central void)", key="in_staircase")
            with p2:
                try:
                    _plan_preview(S["in_width"], S["in_length"], S["in_cantilevers"])
                except Exception as e:  # preview only; the design run reports real errors
                    logger.warning("Plan preview failed: %s", e)
        else:
            st.toggle("Staircase (central void)", key="in_staircase")

    with t_loads:
        st.selectbox("Occupancy (IS 875 Part 2)", list(BUILDING_TYPES), key="in_occupancy",
                     on_change=ui_state.on_occupancy_change)
        lp = get_load_parameters(S["in_occupancy"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Floor live load", f"{lp.live_load_floor_kn_m2} kN/m²", border=True)
        m2.metric("Roof live load", f"{lp.live_load_roof_kn_m2} kN/m²", border=True)
        m3.metric("Finishes + partitions + services",
                  f"{lp.floor_finish_kn_m2 + lp.partition_load_kn_m2 + lp.services_load_kn_m2:.1f} kN/m²", border=True)
        m4.metric("Slab thickness (initial)", f"{lp.slab_thickness_mm:.0f} mm", border=True)
        st.caption("Imposed loads from IS 875 (Part 2) Table 1, checked against the printed standard. Corridors, stairs "
                   "and balconies (3.0 kN/m² residential, 4.0 kN/m² others) are not modelled separately.")
        st.number_input("Wall load (kN/m) — used only when the model has no walls", 0.0, 50.0, step=0.5,
                        key="in_wall_load")

    with t_site:
        st.markdown("**Foundation**")
        st.number_input("Safe bearing capacity, SBC (kN/m²) — from the geotechnical report", min_value=50.0,
                        max_value=1000.0, step=10.0, key="in_sbc", placeholder="Required — not assumed",
                        on_change=ui_state.on_site_change, help="Sizes every footing. No default is assumed.")
        st.markdown("**Seismic — IS 1893 (Part 1)**")
        s1, s2 = st.columns(2)
        s1.selectbox("Seismic zone", SEISMIC_ZONES, key="in_zone", format_func=lambda z: ZONE_DESCRIPTIONS.get(z, z),
                     on_change=ui_state.on_site_change)
        s2.selectbox("Soil type", list(ui_state.SOIL_TYPES), key="in_soil", format_func=ui_state.SOIL_TYPES.get,
                     on_change=ui_state.on_site_change)
        s3, s4 = st.columns(2)
        s3.selectbox("Structural system", list(ui_state.SYSTEMS), key="in_system", format_func=ui_state.SYSTEMS.get,
                     help="R = 5 is valid only with full IS 13920 ductile detailing, verified. StructOptima checks "
                          "end-zone spacing only.")
        s4.number_input("Importance factor I (IS 1893 Table 8)", 1.0, 1.5, step=0.1, key="in_importance",
                        help="Set from the occupancy when it changes (conservative value) — verify against Table 8.")
        st.markdown("**Wind — IS 875 (Part 3)**")
        w1, w2 = st.columns(2)
        w1.selectbox("Wind zone", ["1", "2", "3", "4", "5", "6"], key="in_wind_zone", on_change=ui_state.on_site_change)
        w2.selectbox("Terrain category", ["1", "2", "3", "4"], key="in_terrain", on_change=ui_state.on_site_change)

    with t_mat:
        a1, a2 = st.columns(2)
        a1.radio("Concrete grade", ["M20", "M25", "M30"], key="in_conc", horizontal=True)
        a2.radio("Steel grade", ["Fe415", "Fe500"], key="in_steel", horizontal=True)
        from src.durability import EXPOSURES, requirements as _req
        e1, e2 = st.columns(2)
        e1.selectbox("Exposure condition (IS 456 Table 3)", EXPOSURES, key="in_exposure",
                     help="Mild: protected from weather. Moderate: sheltered from severe rain, buried in non-aggressive "
                          "soil, coastal but sheltered. Severe: severe rain, wetting and drying, coastal. Very severe: "
                          "sea-water spray, aggressive soil. Extreme: tidal zone, aggressive chemicals.")
        e2.selectbox("NBC type of construction (Part 4 Table 1)", [1, 2, 3, 4], key="in_nbc_type",
                     format_func=lambda t: f"Type {t}",
                     help="Sets the fire rating of each element: columns supporting more than one floor 240 / 120 / "
                          "120 / 120 min, beams 180 / 90 / 60 / 60 min, floors 120 / 90 / 60 / 60 min for types 1-4. "
                          "Agree the type with the architect and the fire authority.")
        _r = _req(S["in_exposure"], int(S["in_nbc_type"]), float(S["in_conc"][1:]))
        st.caption(f"Nominal covers used: beams {_r.beam_cover_mm:.0f}, slabs {_r.slab_cover_mm:.0f}, columns "
                   f"{_r.column_cover_mm:.0f}, footings {_r.footing_cover_mm:.0f} mm (IS 456 Tables 16 and 16A). "
                   f"Minimum grade M{_r.min_grade}, max free w/c {_r.max_wc} (Table 5). Fire: columns "
                   f"{_r.column_fire_h:g} h, beams {_r.beam_fire_h:g} h, slabs {_r.slab_fire_h:g} h.")
        b1, b2 = st.columns(2)
        b1.toggle("Fixed column bases", key="in_fixed_base", help="Off = pinned bases in the frame analysis.")
        b2.toggle("Cracked sections (0.70 Ig columns, 0.35 Ig beams)", key="in_cracked")
        b1.toggle("Green concrete (fly ash) for quantities and carbon", key="in_fly_ash")
        b2.toggle("Columns in 230 mm walls: 230 mm side (residential)", key="in_col_match_wall",
                  help="Columns standing in a 230 mm wall line get their side across the wall equal to the wall, "
                       "the other side from the load (450-900 mm). Only in Zone II with OMRF: IS 13920:2016 7.1.1 "
                       "requires 300 mm in Zones III-V and for SMRF. Free-standing columns stay at least 300 x 450. "
                       "Fire check: IS 456 Fig. 1 '50 % exposed'. Turn on interior walls (Masonry tab) for interior "
                       "columns that stand in walls.")
        b2.toggle("Show column optimisation (indicative only)", key="in_optimise")
        st.selectbox("Plan / 3D colouring", ["Engineering", "Architectural", "Utilization", "Load Path"],
                     key="in_view_mode")

    with t_mas:
        k1, k2 = st.columns(2)
        k1.selectbox("Wall thickness (finished)", list(ui_state.WALL_TYPES), key="in_wall_type",
                     format_func=ui_state.WALL_TYPES.get)
        k2.selectbox("Mortar (cement : sand)", list(ui_state.MORTARS), key="in_mortar",
                     format_func=ui_state.MORTARS.get)
        st.slider("Openings (doors / windows) as a fraction of wall area", 0.0, 0.5, step=0.05, key="in_openings")
        k3, k4 = st.columns(2)
        k3.toggle("Include interior partition walls", key="in_interior_walls")
        k4.toggle("Show walls in 3D views", key="in_show_walls")

with right:
    with st.container(border=True):
        st.markdown("#### Run design")
        mode = S["in_mode"]
        h_total = S["in_stories"] * S["in_story_h"]
        size = f"{S['in_width']:.1f} x {S['in_length']:.1f} m plan · " if mode == MODES[0] else ""
        st.caption(f"{size}{S['in_stories']} storeys x {S['in_story_h']:.1f} m = {h_total:.1f} m · Zone {S['in_zone']} · "
                   f"soil {S['in_soil']} · SBC {S['in_sbc'] if S['in_sbc'] is not None else '—'} kN/m²")
        if h_total > 15.0 and mode != MODES[2]:
            st.warning("Above about 15 m: verify the equivalent-static method, P-Δ effects and dynamic wind "
                       "independently. StructOptima uses 2D frames without torsion.", icon=":material/height:")
        st.checkbox("The SBC, seismic zone, soil type, wind zone and terrain category apply to this site "
                    "(geotechnical report, IS 1893 and IS 875 maps).", key="in_site_confirmed")
        st.checkbox("I will verify all outputs independently before use. This tool gives preliminary designs "
                    "that need review by a licensed structural engineer.", key="in_disclaimer")
        missing = ui_state.missing_inputs()
        for m in missing:
            st.markdown(f":orange[:material/radio_button_unchecked:] {m}")
        state = ui_state.results_state()
        run = st.button("Run design" if state == "none" else "Re-run design", type="primary", disabled=bool(missing),
                        width="stretch", icon=":material/play_arrow:")
        if state != "none":
            res = S["design_results"]
            s = design_status_summary(res)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.caption("Last run:")
                status_badge(s["status"], f"{s['status']} · {s['n_fail']} fail · {s['n_warn']} warn")
            if state == "stale":
                st.caption(":orange[Inputs changed since the last run — re-run to update the results.]")
            st.page_link("pages/overview.py", label="Open results", icon=":material/arrow_forward:")

    with st.expander("IS 456 quick reference"):
        render_quick_reference()

if run:
    with st.status("Running analysis and design...", expanded=True) as status:
        st.write("Building the model and solving the frames for every load combination")
        try:
            res = ui_state.run_design_from_inputs()
        except ui_state.InputError as e:
            status.update(label="Input problem", state="error")
            st.error(str(e))
            st.stop()
        except Exception as e:
            logger.error("Design pipeline failed: %s", e)
            capture_exception(e)
            status.update(label="Design failed", state="error")
            st.error(f"Design failed: {e}")
            st.stop()
        status.update(label=f"Design complete — status {res.status}", state="complete")
    st.switch_page("pages/overview.py")
