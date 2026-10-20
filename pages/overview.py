"""Overview: design status, issues to resolve, the 3D model and quantities."""
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.ui_components import require_results, style_status
from src.ui_tables import design_status_summary, issue_rows

require_results()
S = st.session_state
res = S['design_results']
gm = res.gm
bom = res.bom
summary = design_status_summary(res)

# ---- design status (single source of truth: DesignResults.status) ----
if res.status == "FAIL":
    st.error(f"**Design status: FAIL** — {summary['n_fail']} failing item(s), {summary['n_warn']} warning(s). The design "
             f"is not acceptable as it stands. PRELIMINARY — NOT FOR CONSTRUCTION.", icon=":material/cancel:")
elif res.status == "WARN":
    st.warning(f"**Design status: WARN** — {summary['n_warn']} item(s) need engineering review. "
               f"PRELIMINARY — NOT FOR CONSTRUCTION.", icon=":material/warning:")
else:
    st.success("**Design status: PASS** for the implemented checks only — NOT VERIFIED. PRELIMINARY — independent "
               "verification by a licensed structural engineer is required.", icon=":material/check_circle:")
with st.expander(f"Checks NOT performed by StructOptima ({len(res.checks_not_performed)}) — must be done separately"):
    for _c in res.checks_not_performed:
        st.markdown(f"- {_c}")

st.markdown("#### Issues to resolve")
rows = issue_rows(res.failures)
if not rows:
    st.success("No failing or warning items among the implemented checks. This is not a substitute for "
               "independent verification.")
else:
    f1, f2 = st.columns([1, 1.6], vertical_alignment="bottom")
    sel_status = f1.pills("Status", ["FAIL", "WARN"], selection_mode="multi", default=["FAIL", "WARN"],
                          key="ov_status")
    types = sorted({r["Type"] for r in rows})
    sel_types = f2.multiselect("Type", types, placeholder="All types", key="ov_types")
    shown = [r for r in rows if r["Status"] in (sel_status or []) and (not sel_types or r["Type"] in sel_types)]
    if shown:
        df = pd.DataFrame(shown)[["Status", "Type", "Member", "Issue"]]
        st.dataframe(style_status(df), hide_index=True, height=min(38 + 35 * len(df), 400),
                     column_config={"Status": st.column_config.TextColumn(width="small"),
                                    "Type": st.column_config.TextColumn(width="small"),
                                    "Member": st.column_config.TextColumn(width="small"),
                                    "Issue": st.column_config.TextColumn(width="large")})
    else:
        st.caption("No items match the filter.")
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption(f"{len(shown)} of {len(rows)} items · hover a cell to read long text.")
        st.page_link("pages/checks.py", label="All checks", icon=":material/fact_check:")
        st.page_link("pages/members.py", label="Member schedules", icon=":material/view_column:")

left, right = st.columns([1.35, 1], gap="medium")

with left:
    st.markdown("#### Model")
    from src.viewer_model import build_scene, bundle_available, viewer_html
    if bundle_available():
        if S.get('_viewer_key_ov') != id(res):
            S['_viewer_html_ov'] = viewer_html(build_scene(gm, res.beams, res.footings), 440)
            S['_viewer_key_ov'] = id(res)
        components.html(S['_viewer_html_ov'], height=450)
        st.caption("Drag to orbit, scroll to zoom, click a member for its size, bars and status. Full-size viewer, "
                   "plans and drawing sheets on the Drawings & 3D page.")
    else:
        st.info("The 3D viewer bundle (components/viewer3d/dist/viewer.js) is missing.")

with right:
    st.markdown("#### Quantities")
    st.metric("Concrete (all floors)", f"{bom.total_concrete_vol_m3:.1f} m³", border=True,
              help="Wet volume; beam / slab / column overlaps not deducted.")
    st.metric("Reinforcement (all floors)", f"{bom.total_steel_weight_kg:,.0f} kg", border=True,
              help="Includes wastage and rolling margin. The bar bending schedule covers one typical floor only.")
    st.metric("Estimated cost — structure", f"₹ {bom.total_cost_inr:,.0f}", border=True,
              help="From the unit rates in the quantity module; check against current local rates.")
    st.metric("Embodied carbon", f"{bom.total_carbon_kg / 1000.0:.1f} t CO₂e", border=True)

with right.expander(f"Concrete materials for {bom.total_concrete_vol_m3:.1f} m³ ({S.get('conc_grade')})"):
    _mix = S.get('approved_mix')
    if _mix:
        from src.site_calculators import materials_for_mix
        _m = materials_for_mix(bom.total_concrete_vol_m3, _mix)
        st.markdown(f"""
| Material ({_mix['name']}) | Total |
|---|---|
| Cement | **{_m['cement_bags']} bags (50 kg)** |
| Fine aggregate | **{_m['fine_aggregate_t']:.2f} t** |
| Coarse aggregate | **{_m['coarse_aggregate_t']:.2f} t** |
| Water | {_m['water_l']:.0f} L |
""")
    else:
        st.caption("Enter your approved mix design (Site tools → Site calculators → Approved mix) to get cement, sand, "
                   "aggregate and water quantities.")
        st.page_link("pages/site_tools.py", label="Site tools", icon=":material/construction:")
wb = res.wall_bom
if wb:
    with right.expander(f"Masonry and finishes: {wb.total_bricks:,} bricks · "
                        f"{wb.total_mortar_cement_bags + wb.total_plaster_cement_bags} bags cement"):
        wm1, wm2 = st.columns(2)
        wm1.metric("Bricks", f"{wb.total_bricks:,}")
        wm1.caption(f"Wall volume {wb.total_wall_volume_m3:.2f} m³")
        wm2.metric("Mortar cement", f"{wb.total_mortar_cement_bags} bags")
        wm2.caption(f"Sand {wb.total_mortar_sand_tonnes:.2f} t · water {wb.total_mortar_water_litres:.0f} L")
        wm1.metric("Plaster", f"{wb.total_plaster_area_m2:.0f} m²")
        wm1.caption(f"Cement {wb.total_plaster_cement_bags} bags · sand {wb.total_plaster_sand_tonnes:.2f} t")
        wm2.metric("Paint", f"{wb.total_emulsion_int_litres + wb.total_emulsion_ext_litres:.0f} L")
        wm2.caption(f"Primer {wb.total_primer_litres:.1f} L · putty {wb.total_putty_kg:.1f} kg")

notes = [f"ℹ️ {m}" for m in res.messages] + \
        [f"⚠️ Input: {w.get('message', w) if isinstance(w, dict) else w}" for w in S.get('cad_warnings', [])]
a_fail = sum(1 for r in res.audit_results if r.status == "FAIL")
with st.expander(f"Run notes ({len(notes)}) · audit re-check {len(res.audit_results) - a_fail}/{len(res.audit_results)}"):
    st.caption("The audit re-check is a consistency screen of the designed members, not independent verification. "
               "Its failures are already in the issue list.")
    for n in notes:
        st.caption(n)

# ---- column editor (DXF models with automatic column placement) ----
if S.get('editor_placement') is not None:
    from src.column_editor import ColumnEditor, ModificationSeverity
    from src.grid_manager import Column as GMColumn

    story_height = S['story_height']
    num_stories = S['num_stories']

    def _apply_editor_result(new_result):
        S['editor_placement'] = new_result
        base = []
        for col_data in new_result.columns:
            base.append(GMColumn(
                id=col_data.id, x=col_data.x * 0.001, y=col_data.y * 0.001,
                width_nb=col_data.width, depth_nb=col_data.depth,
                junction_type=col_data.junction_type.value, is_floating=col_data.is_floating,
                reinforcement_rule=col_data.reinforcement_rule.value, orientation_deg=col_data.orientation_deg,
                level=0, z_top=story_height))
        gm.columns = gm.stack_columns(base, num_stories, story_height)
        S['gm'] = gm
        S['needs_redesign'] = True

    with st.expander("Column editor — add or remove columns"):
        st.caption("Changes the automatic column layout. A change re-runs the full analysis and design.")
        editor_placement = S['editor_placement']
        col_ids = [c.id for c in editor_placement.columns]

        def _editor():
            return ColumnEditor(
                placement=editor_placement, centerlines=S['editor_centerlines'],
                building_envelope=S['editor_envelope'], seismic_zone=S['editor_seismic_zone'],
                primary_x=S['editor_primary_x'], primary_y=S['editor_primary_y'])

        def _show(val):
            for w in val.warnings:
                if w.severity == ModificationSeverity.CRITICAL:
                    st.error(f"**CRITICAL:** {w.message}")
                elif w.severity == ModificationSeverity.WARNING:
                    st.warning(f"**WARNING:** {w.message}")
                else:
                    st.info(w.message)
                if getattr(w, 'code_reference', None):
                    st.caption(f"Ref: {w.code_reference}")

        edit_tab1, edit_tab2 = st.tabs(["Remove a column", "Add a column"])
        with edit_tab1:
            remove_col_id = st.selectbox("Column to remove", col_ids, key="remove_col_select")
            sel_col = next((c for c in editor_placement.columns if c.id == remove_col_id), None)
            if sel_col:
                st.caption(f"Location ({sel_col.x:.0f}, {sel_col.y:.0f}) mm · {sel_col.junction_type.value} · "
                           f"{sel_col.width:.0f} x {sel_col.depth:.0f} mm")
            if st.button("Check removal", key="validate_remove_btn"):
                editor = _editor()
                S['remove_validation'] = editor.validate_remove_column(remove_col_id)
                S['remove_editor'] = editor
            if 'remove_validation' in S:
                val = S['remove_validation']
                _show(val)
                if val.can_proceed:
                    if st.button("Remove and re-design", key="confirm_remove_btn", type="primary"):
                        _apply_editor_result(S['remove_editor'].remove_column(remove_col_id))
                        del S['remove_validation']
                        del S['remove_editor']
                        st.rerun()
                else:
                    st.error("Removal blocked — resolve the CRITICAL items above first.")
        with edit_tab2:
            add_c1, add_c2 = st.columns(2)
            add_x = add_c1.number_input("X coordinate (mm)", value=0.0, step=100.0, key="add_col_x")
            add_y = add_c2.number_input("Y coordinate (mm)", value=0.0, step=100.0, key="add_col_y")
            if st.button("Check placement", key="validate_add_btn"):
                editor = _editor()
                S['add_validation'] = editor.validate_add_column(add_x, add_y)
                S['add_editor'] = editor
            if 'add_validation' in S:
                val = S['add_validation']
                _show(val)
                if val.can_proceed:
                    if st.button("Add and re-design", key="confirm_add_btn", type="primary"):
                        _apply_editor_result(S['add_editor'].add_column(add_x, add_y))
                        del S['add_validation']
                        del S['add_editor']
                        st.rerun()
