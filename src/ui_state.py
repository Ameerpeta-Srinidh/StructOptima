"""
Project inputs and design-run state for the Streamlit UI.

- Every project input lives in ``st.session_state`` under an ``in_*`` key. ``keep_inputs`` re-assigns
  them on every run so they survive page switches (Streamlit drops the state of widgets that are not
  rendered on the current page).
- ``input_fingerprint`` identifies the inputs a design was run with; result pages compare it with the
  current inputs and say when the results are out of date.
- ``run_design_from_inputs`` builds the model from the inputs and runs ``design_pipeline.run_design``
  (the single source of design status); ``ensure_design`` re-runs it after a column-editor change.

The confirmations (disclaimer, site parameters) are never part of the fingerprint and the site
confirmation is cleared whenever a site parameter changes.
"""
import datetime
import hashlib
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from src.building_types import BUILDING_TYPES, get_load_parameters
from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.logging_config import get_logger
from src.monitoring import capture_exception
from src.seismic import SEISMIC_ZONES, importance_for_occupancy

logger = get_logger(__name__)

MODES = ["Manual dimensions", "CAD drawing (DXF)", "BIM model (IFC)"]
SOIL_TYPES = {"I": "I — Rock / hard soil", "II": "II — Medium soil", "III": "III — Soft soil"}
SYSTEMS = {"OMRF": "OMRF — ordinary moment frame (R = 3)",
           "SMRF": "SMRF — special moment frame (R = 5), needs full IS 13920 verification"}
WALL_TYPES = {"230": "230 mm — full brick / external", "115": "115 mm — half brick / partition"}
MORTARS = {4: "1:4 — standard external", 3: "1:3 — high strength / retaining", 5: "1:5 — general masonry",
           6: "1:6 — internal partition"}
CANTILEVER_SIDES = ["left", "right", "top", "bottom"]

# Site parameters: changing one clears the site confirmation.
SITE_KEYS = ("in_sbc", "in_zone", "in_soil", "in_wind_zone", "in_terrain")
# Inputs that do not change the design (excluded from the fingerprint).
NON_DESIGN_KEYS = ("in_disclaimer", "in_site_confirmed", "in_show_walls", "in_view_mode", "in_optimise", "in_date")


def input_defaults() -> Dict[str, Any]:
    occupancy = next(iter(BUILDING_TYPES))
    return {
        "in_project_name": "Untitled Project",
        "in_engineer": "",
        "in_drawing_ref": "",
        "in_date": datetime.date.today(),
        "in_mode": MODES[0],
        "in_auto_frame": False,
        "in_layer_roles": None,               # DXF layer -> role confirmed by the engineer; None = suggestions
        "in_width": 18.0,
        "in_length": 12.0,
        "in_stories": 2,
        "in_story_h": 3.5,
        "in_occupancy": occupancy,
        "in_wall_load": 12.0,
        "in_sbc": None,                       # never assumed: sizes every footing
        "in_zone": SEISMIC_ZONES[1],
        "in_soil": "II",
        "in_system": "OMRF",
        "in_importance": float(importance_for_occupancy(occupancy)),
        "in_wind_zone": "2",
        "in_terrain": "2",
        "in_wall_type": "230",
        "in_mortar": 4,
        "in_openings": 0.33,
        "in_interior_walls": False,
        "in_show_walls": True,
        "in_staircase": False,
        "in_cantilevers": [],
        "in_fixed_base": True,
        "in_col_match_wall": True,            # D-29: 230 mm column side in 230 mm walls (residential, Zone II OMRF)
        "in_cracked": True,
        "in_conc": "M25",
        "in_exposure": "Moderate",
        "in_nbc_type": 2,
        "in_steel": "Fe415",
        "in_fly_ash": False,
        "in_optimise": False,
        "in_view_mode": "Engineering",
        "in_disclaimer": False,
        "in_site_confirmed": False,
    }


def init_inputs() -> None:
    for k, v in input_defaults().items():
        st.session_state.setdefault(k, v)


def keep_inputs() -> None:
    """Re-assign the input keys so their values survive pages that do not render the widgets."""
    for k in input_defaults():
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def on_site_change() -> None:
    st.session_state["in_site_confirmed"] = False


def on_occupancy_change() -> None:
    st.session_state["in_importance"] = float(importance_for_occupancy(st.session_state["in_occupancy"]))
    on_site_change()


def uploaded_file() -> Optional[Dict[str, Any]]:
    """The CAD/BIM file kept for the current input mode: {"name", "bytes", "kind"} or None."""
    f = st.session_state.get("model_file")
    if f is None:
        return None
    kind = {"CAD drawing (DXF)": "dxf", "BIM model (IFC)": "ifc"}.get(st.session_state.get("in_mode"))
    return f if f["kind"] == kind else None


def input_fingerprint(state=None) -> Tuple:
    s = st.session_state if state is None else state
    items = [(k, repr(s.get(k))) for k in sorted(input_defaults()) if k not in NON_DESIGN_KEYS]
    f = s.get("model_file")
    if f is not None and s.get("in_mode") != MODES[0]:
        items.append(("file", f["name"], hashlib.sha256(f["bytes"]).hexdigest()))
    return tuple(items)


def missing_inputs() -> list:
    """What still blocks a run, in plain words (empty when the run can start)."""
    s = st.session_state
    out = []
    if s.get("in_mode") != MODES[0] and uploaded_file() is None:
        out.append(f"Upload the {'DXF' if s.get('in_mode') == MODES[1] else 'IFC'} file")
    if s.get("in_sbc") is None:
        out.append("Enter the safe bearing capacity (SBC) from the geotechnical report")
    if not s.get("in_site_confirmed"):
        out.append("Confirm that the site parameters apply to this site")
    if not s.get("in_disclaimer"):
        out.append("Accept the verification statement")
    return out


def results_state() -> str:
    """'none', 'current' or 'stale'."""
    if "design_results" not in st.session_state:
        return "none"
    return "current" if st.session_state.get("design_fingerprint") == input_fingerprint() else "stale"


class InputError(Exception):
    """An input problem the user can fix (shown as a message, not a traceback)."""


def _with_temp_file(data: bytes, suffix: str, fn):
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        return fn(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _acquire_geometry(s):
    """Build (gm, beams, loader) from the selected input mode."""
    mode = s["in_mode"]
    if mode == MODES[1]:
        f = uploaded_file()
        if f is None:
            raise InputError("Upload a DXF file.")
        head = f["bytes"][:100]
        if not (b"AutoCAD" in head or b"SECTION" in head or b"  0" in head or b"999" in head):
            raise InputError("This file does not look like a DXF drawing (header check failed).")
        from src.cad_loader import CADLoader

        def load(path):
            loader = CADLoader(path, layer_roles=s.get("in_layer_roles"))
            gm, beams = loader.load_grid_manager(auto_frame=s["in_auto_frame"], seismic_zone=s["in_zone"],
                                                 story_height_m=s["in_story_h"], num_stories=s["in_stories"])
            st.session_state['arch_walls'] = loader.get_architectural_walls()
            st.session_state['cad_warnings'] = list(loader.placement_warnings) + list(loader.load_warnings)
            gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], s["in_stories"], s["in_story_h"])
            return gm, beams, loader
        return _with_temp_file(f["bytes"], ".dxf", load)
    if mode == MODES[2]:
        f = uploaded_file()
        if f is None:
            raise InputError("Upload an IFC file.")
        if b"ISO-10303-21" not in f["bytes"][:100]:
            raise InputError("This file does not look like an IFC model (missing ISO-10303-21 header).")
        from src.bim_loader import BIMLoader

        def load(path):
            loader = BIMLoader(path)
            gm, beams = loader.load_grid_manager()
            st.session_state['cad_warnings'] = list(loader.warnings)
            return gm, beams, loader
        return _with_temp_file(f["bytes"], ".ifc", load)
    gm = GridManager(width_m=s["in_width"], length_m=s["in_length"], num_stories=s["in_stories"],
                     story_height_m=s["in_story_h"])
    gm.cantilever_dirs = list(s["in_cantilevers"])
    gm.cantilever_len_m = 1.5
    gm.generate_grid()
    beams = gm.generate_beams()
    st.session_state['cad_warnings'] = []
    st.session_state['arch_walls'] = None
    return gm, beams, None


def read_dxf(data: bytes, roles: Optional[Dict[str, str]], auto_frame: bool = False) -> Dict[str, Any]:
    """What StructOptima reads from a DXF with the given layer roles (None: suggestions): the layer table, the
    columns / beams / walls in metres as the design will use them, the import warnings, or the input error."""
    from src.cad_loader import CADLoader
    from src.cad_parser import CADParser
    from src.dxf_layers import ROLE_LABELS, analyse_layers

    def run(path):
        out: Dict[str, Any] = {"layers": [], "columns": [], "beams": [], "walls": [], "warnings": [], "error": None}
        suggested = analyse_layers(CADParser(path))
        for i in suggested:
            role = roles.get(i.name, "ignore") if roles is not None else i.role
            out["layers"].append({
                "Layer": i.name, "Holds": i.contents(), "Read as": ROLE_LABELS[role],
                "Why": i.reason if role == i.role else f"set by you (suggested: {ROLE_LABELS[i.role]} - {i.reason})",
                "Confidence": i.confidence if role == i.role else "set by you", "_suggested": i.role})
        try:
            loader = CADLoader(path, layer_roles=roles)
            gm, beams = loader.load_grid_manager(auto_frame=auto_frame)
        except ValueError as e:
            out["error"] = str(e)
            return out
        out["columns"] = [(c.x, c.y, c.width_nb, c.depth_nb, c.id) for c in gm.columns if c.level == 0]
        out["beams"] = [((b.start_point.x, b.start_point.y), (b.end_point.x, b.end_point.y)) for b in beams]
        out["walls"] = [((w.start_x, w.start_y), (w.end_x, w.end_y)) for w in gm.walls]
        out["warnings"] = [w if isinstance(w, str) else w.get("message", str(w))
                           for w in list(loader.placement_warnings) + list(loader.load_warnings)]
        return out
    return _with_temp_file(data, ".dxf", run)


@st.cache_data(max_entries=8, show_spinner="Reading the drawing...")
def read_dxf_cached(data: bytes, roles_items: Optional[Tuple[Tuple[str, str], ...]], auto_frame: bool):
    return read_dxf(data, dict(roles_items) if roles_items is not None else None, auto_frame)


def _design_inputs(s, gm) -> DesignInputs:
    from src.wind_load import TerrainCategory, WindZone
    bim = s["in_mode"] == MODES[2]
    return DesignInputs(
        num_stories=gm.num_stories if bim else s["in_stories"],
        story_height_m=gm.story_height_m if bim else s["in_story_h"],
        building_type_name=s["in_occupancy"], wall_load_kn_m=s["in_wall_load"], sbc_kn_m2=s["in_sbc"],
        conc_grade=s["in_conc"], fy=float(s["in_steel"].replace("Fe", "")), seismic_zone=s["in_zone"],
        soil_type=s["in_soil"], structural_system=s["in_system"], importance_factor=s["in_importance"],
        wind_zone=WindZone(s["in_wind_zone"]), terrain_category=TerrainCategory(s["in_terrain"]),
        use_cracked_sections=s["in_cracked"], fixed_base=s["in_fixed_base"], add_staircase=s["in_staircase"],
        wall_core_thickness_mm=200.0 if s["in_wall_type"] == "230" else 100.0, mortar_ratio=int(s["in_mortar"]),
        wall_opening_fraction=s["in_openings"], include_interior_walls=s["in_interior_walls"],
        use_fly_ash=s["in_fly_ash"], project_name=s["in_project_name"], exposure=s["in_exposure"],
        column_matches_wall=None if s["in_col_match_wall"] else False,
        nbc_construction_type=int(s["in_nbc_type"]))


def _store_results(res, inputs: DesignInputs) -> None:
    s = st.session_state
    from src.materials import Concrete
    s.update({
        'analysis_done': True,
        'needs_redesign': False,
        'design_inputs': inputs,
        'design_fingerprint': input_fingerprint(),
        'design_results': res,
        'design_status': res.status,
        'design_failures': res.failures,
        'design_messages': res.messages,
        'analysis_summary': res.analysis_summary,
        'gm': res.gm,
        'beams': res.beams,
        'all_beams': res.all_beams,
        'footings': res.footings,
        'bom': res.bom,
        'audit_results': res.audit_results,
        'auditor_math': res.auditor_math,
        'project_bbs': res.project_bbs,
        'seismic_result': res.seismic_result,
        'wind_result': res.wind_result,
        'stab_checks': res.stab_checks,
        'stab_summary': res.stab_summary,
        'safety_summary': res.safety_summary,
        'conc_grade': inputs.conc_grade,
        'fck': int(inputs.conc_grade[1:]),
        'fy': inputs.fy,
        'm_grade': Concrete.from_grade(inputs.conc_grade),
        'num_stories': inputs.num_stories,
        'story_height': inputs.story_height_m,
        'project_name': s["in_project_name"],
        'engineer_name': s["in_engineer"],
        'drawing_ref': s["in_drawing_ref"],
        'live_load': get_load_parameters(inputs.building_type_name).live_load_floor_kn_m2,
        'load_params': get_load_parameters(inputs.building_type_name),
        'wall_load': inputs.wall_load_kn_m,
        'sbc': inputs.sbc_kn_m2,
        'seismic_zone': inputs.seismic_zone,
        'soil_type': inputs.soil_type,
        'structural_system': inputs.structural_system,
        'wind_zone': inputs.wind_zone,
        'terrain_cat_enum': inputs.terrain_category,
        'building_type_name': inputs.building_type_name,
        'building_weight': res.building_weight,
        'use_fly_ash': inputs.use_fly_ash,
        'use_cracked': inputs.use_cracked_sections,
        'add_staircase': inputs.add_staircase,
        'sorted_cols': sorted(res.gm.columns, key=lambda c: (c.x, c.y, c.level)),
        'level_0_cols': [c for c in res.gm.columns if c.level == 0],
        'wall_bom': res.wall_bom,
        'wall_core_thickness_mm': inputs.wall_core_thickness_mm,
        'mortar_ratio': inputs.mortar_ratio,
        'wall_opening_fraction': inputs.wall_opening_fraction,
    })


def run_design_from_inputs():
    """Build the model from the current inputs and run the design. Raises InputError for fixable input problems."""
    s = st.session_state
    from src.grid_manager import check_plan_geometry
    try:
        gm, beams, loader = _acquire_geometry(s)
        check_plan_geometry(gm, beams)
    except ValueError as e:             # loaders and the geometry check raise ValueError for a fixable drawing
        raise InputError(str(e)) from e
    s['geometry_beams'] = [b.model_copy(deep=True) for b in beams]
    if loader is not None and getattr(loader, 'placer', None) is not None:
        s['editor_centerlines'] = loader.framer.centerlines
        s['editor_envelope'] = loader.placer.building_envelope
        s['editor_primary_x'] = loader.placer.primary_x
        s['editor_primary_y'] = loader.placer.primary_y
        s['editor_placement'] = loader.placement_result
        s['editor_seismic_zone'] = s["in_zone"]
    else:
        s['editor_placement'] = None
    inputs = _design_inputs(s, gm)
    from src.design_pipeline import InvalidInputError
    from src.grid_manager import InvalidStructureError
    try:
        res = run_design(gm, beams, inputs)
    except (InvalidStructureError, InvalidInputError) as e:  # fixable inputs, not crashes
        raise InputError(str(e)) from e
    _store_results(res, inputs)
    return res


def ensure_design() -> None:
    """Re-run the design with the stored model after a column-editor change (same inputs as the last run)."""
    s = st.session_state
    if not s.get('needs_redesign') or 'gm' not in s or 'design_inputs' not in s:
        return
    fingerprint = s.get('design_fingerprint')
    with st.spinner("Re-designing with the edited column layout..."):
        beams = [b.model_copy(deep=True) for b in s.get('geometry_beams', [])]
        try:
            res = run_design(s['gm'], beams, s['design_inputs'])
        except Exception as e:  # shown to the user; the previous results are discarded
            logger.error("Re-design failed: %s", e)
            capture_exception(e)
            for k in ('design_results', 'analysis_done'):
                s.pop(k, None)
            s['needs_redesign'] = False
            s['run_error'] = f"Re-design failed: {e}"
            return
    _store_results(res, s['design_inputs'])
    s['design_fingerprint'] = fingerprint
