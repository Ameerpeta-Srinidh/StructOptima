import streamlit as st
import sys
import os
import math
import tempfile

# Ensure src path is visible
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Initialize logging and monitoring BEFORE other imports
from src.logging_config import setup_streamlit_logging, get_logger
from src.monitoring import init_sentry_for_streamlit, capture_exception, set_streamlit_context

# Setup logging (console only for Streamlit)
setup_streamlit_logging()
logger = get_logger(__name__)

# Initialize Sentry if configured (set SENTRY_DSN env var to enable)
init_sentry_for_streamlit()

from src.grid_manager import GridManager
from src.materials import Concrete
from src.foundation_eng import design_footing
from src.quantifier import Quantifier
from src.visualizer import Visualizer
from src.report_gen import ReportGenerator
from src.bbs_report import BBSReportGenerator, generate_bbs_from_grid_manager
from src.framing_logic import StructuralMember, Point, MemberProperties
from src.exporters import ExcelExporter
from src.building_types import BUILDING_TYPES, get_load_parameters, get_design_load_summary
from src.optimizer import optimize_structure, OptimizationLevel
from src.stability import run_stability_check, FireRating, FIRE_RESISTANCE_TABLE
from src.anchorage import AnchorageCalculator, get_development_length_table
from src.seismic import run_seismic_check, SEISMIC_ZONES, ZONE_DESCRIPTIONS
from src.safety_warnings import run_safety_warnings_check
from src.bbs_utils import BBSUtils, BendDeductionType, HookType
from src.documentation import DesignReportGenerator
from src.bim_interop import CobieExporter
from src.site_inspection import SiteInspectionManager
from src.shm_module import SHMPlanner
from src.ui_components import inject_css, render_project_header, render_metric_card, render_section_header, render_page_nav_cards, render_is_code_reference

# --- Caching Wrappers for Expensive Operations (Phase 2) ---
@st.cache_data(show_spinner="Optimizing structure...")
def get_optimized_structure(columns, story_height, num_stories, fck):
    return optimize_structure(columns, story_height, num_stories, fck=fck, enable_optimization=True)

@st.cache_data(show_spinner="Running stability & fire checks...")
def get_stability_check_results(columns, all_beams, num_stories, story_height):
    return run_stability_check(columns, all_beams, num_stories, story_height)

@st.cache_data(show_spinner=False)
def get_safety_warnings_results(columns, all_beams, floor_width, floor_length, fck, seismic_zone):
    from src.safety_warnings import run_safety_warnings_check
    return run_safety_warnings_check(columns, all_beams, footings_or_width=floor_width, floor_length=floor_length, fck=fck, seismic_zone=seismic_zone)

# --- App Layout ---

st.set_page_config(page_title="StructOptima — Dashboard", layout="wide", page_icon="🏗️")

inject_css()

# ========== WELCOME BANNER ==========
st.markdown("""
<div style="background: #FFFFFF; padding: 28px 30px; border-radius: 12px; margin-bottom: 20px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.08); border: 1px solid #E2E8F0;
            border-left: 5px solid #1565C0;">
    <h1 style="color: #1A1A2E; margin: 0 0 10px 0; font-size: 2.2em; letter-spacing: -0.5px; font-weight: 700;">
        🏗️ StructOptima
    </h1>
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <span style="background: #E3F2FD; color: #1565C0; padding: 5px 14px;
                     border-radius: 20px; font-weight: 600; font-size: 0.85em;
                     border: 1px solid #BBDEFB;">IS 456:2000</span>
        <span style="background: #E3F2FD; color: #1565C0; padding: 5px 14px;
                     border-radius: 20px; font-weight: 600; font-size: 0.85em;
                     border: 1px solid #BBDEFB;">IS 1893:2016</span>
        <span style="background: #E3F2FD; color: #1565C0; padding: 5px 14px;
                     border-radius: 20px; font-weight: 600; font-size: 0.85em;
                     border: 1px solid #BBDEFB;">IS 13920:2016</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ========== SAMPLE REPORT DOWNLOAD ==========
import os as _os
_sample_report_path = _os.path.join(_os.path.dirname(__file__), "sample_report.pdf")
if _os.path.exists(_sample_report_path):
    with open(_sample_report_path, "rb") as _f:
        _sample_data = _f.read()
    st.download_button(
        label="📄 View Sample Report — No login required",
        data=_sample_data,
        file_name="StructOptima_Sample_Report.pdf",
        mime="application/pdf",
        key="sample_report_btn"
    )

st.markdown("---")

# Sidebar Steps
with st.sidebar:
    st.markdown("### 🏗️ StructOptima")
    st.caption("v1.0.0 · Srinidh Ameerpeta & Charan Tej")
    st.markdown("---")
    
    st.header("Project Details")
    project_name = st.text_input("Project Name", value="Untitled Project", help="Name for reports and exports")
    engineer_name = st.text_input("Structural Engineer", value="", help="Name of the responsible engineer")
    drawing_ref = st.text_input("Drawing Ref. No.", value="", help="Drawing or job reference number")
    project_date = st.date_input("Date")
    st.markdown("---")
    
    with st.expander("📐 Input & Geometry", expanded=True):
        input_mode = st.radio("Input Method", ["Manual Dimensions", "Import CAD (DXF)", "Import BIM (IFC)"], label_visibility="collapsed")
        
        cad_file = None
        auto_frame = False
        width = 0.0
        length = 0.0
        
        if input_mode == "Import CAD (DXF)":
            cad_file = st.file_uploader("Upload DXF File", type=["dxf"])
            auto_frame = st.checkbox("Auto-Frame from Architecture", help="Check this if your file has only walls and you want AI to place columns.")
            st.divider()
            num_stories = st.number_input("Number of Stories", min_value=1, max_value=50, value=2)
            story_height = st.number_input("Story Height (m)", 2.4, 6.0, 3.5)
            
        elif input_mode == "Import BIM (IFC)":
            try:
                import ifcopenshell
                _ifc_available = True
            except ImportError:
                _ifc_available = False
            
            if _ifc_available:
                ifc_file = st.file_uploader("Upload IFC File", type=["ifc"])
                st.info("BIM Mode extracts Material & Geometry from IfcColumn/IfcBeam.")
            else:
                ifc_file = None
                st.error("**IFC import requires `ifcopenshell`** (pip install ifcopenshell)")
                st.stop()
            
        else:
            width = st.slider("Floor Width (m)", 6.0, 50.0, 18.0, 1.0)
            length = st.slider("Floor Length (m)", 6.0, 50.0, 12.0, 1.0)
            st.divider()
            num_stories = st.number_input("Number of Stories", min_value=1, max_value=50, value=2)
            story_height = st.number_input("Story Height (m)", 2.4, 6.0, 3.5)
    
    with st.expander("🏢 Occupancy & Loads", expanded=False):
        building_type_name = st.selectbox(
            "Occupancy Type (IS 875 Part 2)",
            list(BUILDING_TYPES.keys()),
            index=0
        )
        load_params = get_load_parameters(building_type_name)
        live_load = load_params.total_floor_load_kn_m2 + (25 * load_params.slab_thickness_mm / 1000)
        wall_load = st.number_input("Wall Load (kN/m)", 0.0, 50.0, 12.0)
        sbc = st.number_input("SBC (kN/m²)", min_value=50.0, max_value=500.0, value=200.0)
        
    with st.expander("🧱 Wall & Masonry Settings", expanded=False):
        wall_thickness_choice = st.selectbox(
            "Wall Thickness (finished)",
            ["230 mm (Full Brick / External)", "115 mm (Half Brick / Partition)"],
            index=0,
            help="230mm has 200mm core brick + 15mm plaster each side. 115mm has 100mm core brick + 12mm plaster each side."
        )
        wall_core_thickness_mm = 200.0 if "230" in wall_thickness_choice else 100.0
        
        mortar_ratio_choice = st.selectbox(
            "Mortar Proportion (Cement : Sand)",
            ["1:4 (Standard External)", "1:3 (High Strength / Retaining)", "1:5 (General Masonry)", "1:6 (Internal Partition)"],
            index=0,
            help="IS 2250 mortar mix proportions. Cement:Sand = 1:4 is standard for exterior brickwork."
        )
        mortar_ratio = int(mortar_ratio_choice.split(":")[1].split()[0])
        
        wall_opening_fraction = st.slider(
            "Opening Deduction (Doors/Windows)",
            0.0, 0.5, 0.33, 0.05,
            format="%.2f",
            help="Fraction of wall area deducted for doors and windows per IS 1200."
        )
        include_interior_walls = st.checkbox("Include Interior Partition Walls", value=False, help="Generate internal partition walls along interior grid lines.")
        show_3d_walls_default = st.checkbox("Show Walls in 3D Views", value=True)
        
    with st.expander("🌍 Environmental (Seismic & Wind)", expanded=False):
        seismic_zone = st.selectbox(
            "Seismic Zone (IS 1893:2016)",
            SEISMIC_ZONES,
            index=1,
            format_func=lambda x: ZONE_DESCRIPTIONS.get(x, x)
        )
        st.divider()
        wind_zone_idx = st.selectbox("Wind Zone (IS 875 Part 3)", ["1", "2", "3", "4", "5", "6"], index=1)
        from src.wind_load import WindZone, TerrainCategory
        wind_zone = WindZone(wind_zone_idx)
        terrain_cat = st.selectbox("Terrain Category", ["1", "2", "3", "4"], index=1)
        terrain_cat_enum = TerrainCategory(terrain_cat)
        
    with st.expander("⚙️ Advanced Settings", expanded=False):
        add_staircase = st.checkbox("Add Staircase (Central Void)")
        cant_dirs = []
        if input_mode == "Manual Dimensions":
            st.caption("Cantilever Balconies:")
            c_left, c_right = st.columns(2)
            if c_left.checkbox("Left"): cant_dirs.append("left")
            if c_right.checkbox("Right"): cant_dirs.append("right")
            c_top, c_bot = st.columns(2)
            if c_top.checkbox("Top (Back)"): cant_dirs.append("top")
            if c_bot.checkbox("Bottom (Front)"): cant_dirs.append("bottom")
            st.divider()
            
        assume_fixed = st.checkbox("Fixed Supports (Base)", value=True)
        use_cracked = st.checkbox("Cracked Sections", value=True, help="0.7Ig Col, 0.35Ig Beam")
        conc_grade = st.selectbox("Concrete Grade", ["M20", "M25", "M30"], index=1)
        use_fly_ash = st.checkbox("Use Green Concrete (Fly Ash)")
        enable_optimization = st.checkbox("Enable Cost Optimization", value=False)
        view_mode = st.selectbox("View Mode", ["Engineering", "Architectural", "Deflection", "Utilization", "Load Path"], index=0)

    st.markdown("<br>", unsafe_allow_html=True)
    _disclaimer_accepted = st.checkbox(
        "I confirm that I will independently verify all outputs before use in construction. "
        "I understand this tool provides preliminary structural designs that require review "
        "by a licensed Structural Engineer.",
        key="disclaimer_checkbox"
    )
    
    run_btn = st.button(
        "Run Analysis", 
        type="primary", 
        disabled=not _disclaimer_accepted,
        help="Accept the professional use disclaimer above to enable analysis"
    )
    if not _disclaimer_accepted:
        st.caption("☝️ Please accept the disclaimer to proceed")
        
    render_is_code_reference()

# Main Execution Logic
if run_btn:
    st.session_state['analysis_done'] = True
    
if st.session_state.get('analysis_done', False):
    with st.spinner("Analyzing Structure..."):
        if run_btn or 'gm' not in st.session_state:
            gm = None
            beams = []
            
            if input_mode == "Import CAD (DXF)":
                if cad_file is None:
                    st.error("Please upload a DXF file.")
                    st.stop()
                    
                header = cad_file.getvalue()[:100]
                if not (b"AutoCAD" in header or b"SECTION" in header or b"  0" in header or b"999" in header):
                    st.error("Invalid DXF file. Security check failed: Magic bytes do not match expected DXF format.")
                    st.stop()
                    
                tmp_file = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False)
                tmp_file.write(cad_file.getbuffer())
                tmp_file.close()
                temp_filename = tmp_file.name
                    
                from src.cad_loader import CADLoader
                try:
                    loader = CADLoader(temp_filename)
                    gm, beams = loader.load_grid_manager(auto_frame=auto_frame)
                    
                    st.session_state['arch_walls'] = loader.get_architectural_walls()
                    
                    if auto_frame and not beams:
                        beams = gm.generate_beams()
                            
                    if not gm.walls and hasattr(gm, 'generate_walls'):
                        gm.generate_walls(
                            wall_thickness_mm=wall_core_thickness_mm,
                            opening_fraction=wall_opening_fraction,
                            include_interior=include_interior_walls
                        )
                            
                    gm.num_stories = num_stories
                    gm.story_height_m = story_height
                    
                    base_cols = [c for c in gm.columns] 
                    gm.columns = [] 
                    
                    for level in range(num_stories):
                        z_bot = level * story_height
                        z_top = (level + 1) * story_height
                        
                        for base_c in base_cols:
                            new_c = base_c.model_copy()
                            new_c.id = f"{base_c.id}_L{level}"
                            new_c.level = level
                            new_c.z_bottom = z_bot
                            new_c.z_top = z_top
                            gm.columns.append(new_c)
                    
                except Exception as e:
                    logger.error("Failed to load CAD file: %s", e)
                    capture_exception(e)
                    st.error(f"Failed to load CAD: {e}")
                    st.stop()
                finally:
                    try:
                        os.unlink(temp_filename)
                    except OSError:
                        pass
            
            elif input_mode == "Import BIM (IFC)":
                if ifc_file is None:
                    st.error("Please upload an IFC file.")
                    st.stop()
                    
                header = ifc_file.getvalue()[:100]
                if b"ISO-10303-21" not in header:
                    st.error("Invalid IFC file. Security check failed: Missing ISO-10303-21 STEP signature.")
                    st.stop()
                    
                tmp_file = tempfile.NamedTemporaryFile(suffix='.ifc', delete=False)
                tmp_file.write(ifc_file.getbuffer())
                tmp_file.close()
                temp_filename = tmp_file.name
                
                from src.bim_loader import BIMLoader
                try:
                    loader = BIMLoader(temp_filename)
                    gm, beams = loader.load_grid_manager()
                except Exception as e:
                    logger.error("Failed to load IFC file: %s", e)
                    capture_exception(e)
                    st.error(f"Failed to load IFC: {e}")
                    st.stop()
                finally:
                    try:
                        os.unlink(temp_filename)
                    except OSError:
                        pass
            
            else:
                gm = GridManager(
                    width_m=width, 
                    length_m=length, 
                    num_stories=num_stories,
                    story_height_m=story_height
                )
                gm.cantilever_dirs = cant_dirs
                gm.cantilever_len_m = 1.5
                gm.generate_grid()
                beams = gm.generate_beams()
                gm.generate_walls(
                    wall_thickness_mm=wall_core_thickness_mm,
                    opening_fraction=wall_opening_fraction,
                    include_interior=include_interior_walls,
                    slab_thickness_mm=load_params.slab_thickness_mm if hasattr(load_params, 'slab_thickness_mm') else 125.0,
                )
            
            st.session_state['gm'] = gm
            st.session_state['beams'] = beams
            
            if ('loader' in locals() and hasattr(loader, 'placer') 
                    and loader.placer is not None):
                st.session_state['editor_centerlines'] = loader.framer.centerlines
                st.session_state['editor_envelope'] = loader.placer.building_envelope
                st.session_state['editor_primary_x'] = loader.placer.primary_x
                st.session_state['editor_primary_y'] = loader.placer.primary_y
                st.session_state['editor_placement'] = loader.placement_result
                st.session_state['editor_seismic_zone'] = seismic_zone
        else:
            gm = st.session_state['gm']
            beams = st.session_state['beams']
            
        staircase_bay = None
        if add_staircase:
            mid_x = len(gm.x_grid_lines) // 2
            mid_y = len(gm.y_grid_lines) // 2
            mid_x = max(0, min(mid_x, len(gm.x_grid_lines)-2))
            mid_y = max(0, min(mid_y, len(gm.y_grid_lines)-2))
            staircase_bay = (mid_x, mid_y)
            
        gm.calculate_trib_areas(staircase_bay=staircase_bay)
        gm.calculate_loads(floor_load_kn_m2=live_load, wall_load_kn_m=wall_load)
        
        from src.analysis_integration import update_structural_analysis
        update_structural_analysis(gm, beams, use_cracked_sections=use_cracked)
        
        m_grade = Concrete.from_grade(conc_grade)
        _residential_types = ["Residential", "Residential (IS 875)", "Apartment", "Housing"]
        _is_residential = any(r.lower() in building_type_name.lower() for r in ["residential", "apartment", "housing", "flat", "dwelling"])
        gm.optimize_column_sizes(
            concrete=m_grade, 
            fy=415.0,
            wall_thickness_mm=wall_core_thickness_mm,
            align_to_wall=_is_residential,
            seismic_zone=seismic_zone
        )
        gm.detail_columns(concrete=m_grade, fy=415.0)
        gm.detail_beams(beams)
        gm.detail_slabs()
        
        if add_staircase:
            gm.detail_staircase()
            
        level_0_cols = [c for c in gm.columns if c.level == 0]
        footings = []
        for col in level_0_cols:
            ft = design_footing(
                axial_load_kn=col.load_kn, 
                sbc_kn_m2=sbc, 
                column_width_mm=col.width_nb, 
                column_depth_mm=col.depth_nb, 
                concrete=m_grade
            )
            footings.append(ft)
        
        all_beams = []
        for i in range(num_stories):
            for b in beams:
                copied = b.model_copy(deep=True)
                copied.id = f"{b.id}_L{i}"
                copied.level = i
                all_beams.append(copied)
                
        project_bbs = generate_bbs_from_grid_manager(gm, all_beams, "Residential Project")
            
        quantifier = Quantifier()
        bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=use_fly_ash)
        
        from src.wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=mortar_ratio, wc_ratio=0.50, opening_fraction=wall_opening_fraction)
        wall_bom = wall_calc.calculate_all(
            gm.walls,
            num_stories=num_stories,
            floor_height_m=story_height,
            slab_thickness_mm=load_params.slab_thickness_mm if hasattr(load_params, 'slab_thickness_mm') else 125.0,
            beam_depth_mm=400.0,
        )
        st.session_state['wall_bom'] = wall_bom
        
        from src.audit import StructuralAuditor
        auditor = StructuralAuditor(gm, all_beams, footings)
        audit_results = auditor.run_audit()

        sorted_cols = sorted(gm.columns, key=lambda c: (c.x, c.y, c.level))
        
        fck = int(conc_grade[1:])
        floor_area_m2 = gm.width_m * gm.length_m
        dead_load_per_floor = bom.total_concrete_vol_m3 * 25 / max(num_stories, 1)  # DL per floor
        ll_per_m2 = load_params.live_load_kn_m2 if hasattr(load_params, 'live_load_kn_m2') else 2.0
        ll_fraction = 0.25 if ll_per_m2 <= 3.0 else 0.50  # IS 1893 Table 10
        building_weight = bom.total_concrete_vol_m3 * 25  # Total DL (concrete includes steel density)
        for lvl in range(num_stories):
            if lvl == num_stories - 1:  # Roof
                building_weight += 0  # 0% LL on roof
            else:
                building_weight += floor_area_m2 * ll_per_m2 * ll_fraction

        seismic_result = run_seismic_check(
            gm.columns,
            all_beams,
            building_weight,
            zone=seismic_zone,
            building_type=building_type_name.lower().split()[0],
            fck=fck
        )
        
        from src.wind_load import calculate_wind_load
        wind_result = calculate_wind_load(
            zone=wind_zone,
            height_m=num_stories * story_height,
            width_m=gm.width_m,
            length_m=gm.length_m,
            terrain_category=terrain_cat_enum,
            opening_percentage=10.0
        )
        
        stab_checks, stab_summary = get_stability_check_results(
            gm.columns,
            all_beams,
            num_stories,
            story_height
        )
        
        safety_summary = get_safety_warnings_results(
            gm.columns,
            all_beams,
            floor_width=gm.width_m,
            floor_length=gm.length_m,
            fck=fck,
            seismic_zone=seismic_zone
        )

        st.session_state['analysis_done'] = True
        st.session_state['gm'] = gm
        st.session_state['beams'] = beams
        st.session_state['all_beams'] = all_beams
        st.session_state['footings'] = footings
        st.session_state['bom'] = bom
        st.session_state['audit_results'] = audit_results
        st.session_state['auditor_math'] = auditor.math_breakdown
        st.session_state['project_bbs'] = project_bbs
        st.session_state['seismic_result'] = seismic_result
        st.session_state['wind_result'] = wind_result
        st.session_state['stab_checks'] = stab_checks
        st.session_state['stab_summary'] = stab_summary
        st.session_state['safety_summary'] = safety_summary
        st.session_state['m_grade'] = m_grade
        st.session_state['conc_grade'] = conc_grade
        st.session_state['fck'] = fck
        st.session_state['num_stories'] = num_stories
        st.session_state['story_height'] = story_height
        st.session_state['project_name'] = project_name
        st.session_state['engineer_name'] = engineer_name
        st.session_state['drawing_ref'] = drawing_ref
        st.session_state['live_load'] = live_load
        st.session_state['wall_load'] = wall_load
        st.session_state['sbc'] = sbc
        st.session_state['view_mode'] = view_mode
        st.session_state['seismic_zone'] = seismic_zone
        st.session_state['wind_zone'] = wind_zone
        st.session_state['terrain_cat_enum'] = terrain_cat_enum
        st.session_state['building_type_name'] = building_type_name
        st.session_state['building_weight'] = building_weight
        st.session_state['enable_optimization'] = enable_optimization
        st.session_state['use_fly_ash'] = use_fly_ash
        st.session_state['sorted_cols'] = sorted_cols
        st.session_state['level_0_cols'] = level_0_cols
        st.session_state['use_cracked'] = use_cracked
        st.session_state['load_params'] = load_params
        st.session_state['arch_walls'] = st.session_state.get('arch_walls')
        st.session_state['add_staircase'] = add_staircase
        st.session_state['wall_bom'] = wall_bom
        st.session_state['wall_thickness_choice'] = wall_thickness_choice
        st.session_state['wall_core_thickness_mm'] = wall_core_thickness_mm
        st.session_state['mortar_ratio'] = mortar_ratio
        st.session_state['wall_opening_fraction'] = wall_opening_fraction
        st.session_state['show_3d_walls'] = show_3d_walls_default

    render_project_header()
    
    # 4 metric cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.expander(f"🏢 Total Concrete: {bom.total_concrete_vol_m3:.2f} m³", expanded=False):
            from src.site_calculators import mix_design_table
            _mix = mix_design_table(conc_grade or "M25")
            vol = bom.total_concrete_vol_m3
            dry_factor = 1.54  # IS 10262 dry volume factor
            _fck_key = int((conc_grade or "M25").replace("M", ""))
            _wc = _mix["water_cement_ratio"]
            _cement_per_m3 = _mix["cement_kg_m3"]
            _fa_per_m3 = _mix["fine_aggregate_kg_m3"] / 1600.0  # kg→m³ (bulk density ~1600)
            _ca_per_m3 = _mix["coarse_aggregate_kg_m3"] / 1450.0  # kg→m³ (bulk density ~1450)
            total_cement_bags = round(vol * _mix["cement_bags_per_m3"], 1)
            total_fa_m3 = round(vol * _fa_per_m3, 2)
            total_ca_m3 = round(vol * _ca_per_m3, 2)
            st.caption(f"**Grade:** {conc_grade or 'M25'} | **W/C Ratio:** {_wc}")
            st.caption(f"**Wet Volume:** {vol:.2f} m³")
            st.markdown(f"""
| Material | Per m³ | Total |
|---|---|---|
| Cement | {_mix['cement_bags_per_m3']} bags | **{total_cement_bags} bags (50kg)** |
| Fine Aggregate | {_fa_per_m3:.3f} m³ | **{total_fa_m3} m³** |
| Coarse Aggregate | {_ca_per_m3:.3f} m³ | **{total_ca_m3} m³** |
| Water | {_mix['water_kg_m3']} kg | {round(vol * _mix['water_kg_m3'], 0):.0f} kg |
""")
            st.caption("Ref: IS 10262:2019 Concrete Mix Design")
    with c2:
        render_metric_card("Total Steel", f"{bom.total_steel_weight_kg:.0f} kg", icon="🔩")
    with c3:
        render_metric_card("Est. Cost", f"INR {bom.total_cost_inr:,.2f}", icon="💰")
    with c4:
        render_metric_card("Carbon Footprint", f"{bom.total_carbon_kg/1000.0:.2f} Tons", icon="🌱")
        
    if st.session_state.get('wall_bom'):
        wb = st.session_state['wall_bom']
        total_cem_bags = wb.total_mortar_cement_bags + wb.total_plaster_cement_bags
        with st.expander(f"🧱 Masonry & Finishes: {wb.total_bricks:,} Bricks | {total_cem_bags} Bags Cement | {wb.total_plaster_area_m2:.1f} m² Plaster", expanded=False):
            wm1, wm2, wm3, wm4 = st.columns(4)
            with wm1:
                st.metric("Total Bricks", f"{wb.total_bricks:,} pcs")
                st.caption(f"Wall Vol: {wb.total_wall_volume_m3:.2f} m³")
            with wm2:
                st.metric("Mortar (Wet)", f"{wb.total_mortar_cement_bags} bags cement")
                st.caption(f"Sand: {wb.total_mortar_sand_tonnes:.2f} T | Water: {wb.total_mortar_water_litres:.0f} L")
            with wm3:
                st.metric("Plastering", f"{wb.total_plaster_area_m2:.1f} m²")
                st.caption(f"Cement: {wb.total_plaster_cement_bags} bags | Sand: {wb.total_plaster_sand_tonnes:.2f} T")
            with wm4:
                st.metric("Paint / Putty", f"{wb.total_emulsion_int_litres + wb.total_emulsion_ext_litres:.1f} L")
                st.caption(f"Primer: {wb.total_primer_litres:.1f} L | Putty: {wb.total_putty_kg:.1f} kg")
        
    failed_checks = [r for r in audit_results if r.status == "FAIL"]
    pass_count = len(audit_results) - len(failed_checks)
    if failed_checks:
        st.error(f"❌ {pass_count}/{len(audit_results)} audit checks pass")
    else:
        st.success(f"✅ {pass_count}/{len(audit_results)} audit checks pass")
        
    render_page_nav_cards()

    # Column Editor UI
    if st.session_state.get('editor_placement') is not None:
        from src.column_editor import ColumnEditor, ModificationSeverity
        with st.expander("✏️ Column Editor — Add or Remove Columns", expanded=False):
            st.caption("Modify the auto-generated column layout. The system will validate structural integrity per IS 456:2000.")
            editor_placement = st.session_state['editor_placement']
            col_ids = [c.id for c in editor_placement.columns]
            edit_tab1, edit_tab2 = st.tabs(["🗑️ Remove Column", "➕ Add Column"])
            with edit_tab1:
                st.markdown("**Select a column to remove.** The system will check if removal is structurally safe.")
                remove_col_id = st.selectbox("Column to Remove", col_ids, key="remove_col_select")
                sel_col = next((c for c in editor_placement.columns if c.id == remove_col_id), None)
                if sel_col:
                    st.caption(f"📍 Location: ({sel_col.x:.0f}, {sel_col.y:.0f}) mm | Type: {sel_col.junction_type.value} | Size: {sel_col.width:.0f}×{sel_col.depth:.0f} mm")
                if st.button("🔍 Validate Removal", key="validate_remove_btn"):
                    editor = ColumnEditor(
                        placement=editor_placement, centerlines=st.session_state['editor_centerlines'],
                        building_envelope=st.session_state['editor_envelope'], seismic_zone=st.session_state['editor_seismic_zone'],
                        primary_x=st.session_state['editor_primary_x'], primary_y=st.session_state['editor_primary_y']
                    )
                    val_result = editor.validate_remove_column(remove_col_id)
                    st.session_state['remove_validation'] = val_result
                    st.session_state['remove_editor'] = editor
                if 'remove_validation' in st.session_state:
                    val = st.session_state['remove_validation']
                    for w in val.warnings:
                        if w.severity == ModificationSeverity.CRITICAL:
                            st.error(f"🚫 **CRITICAL:** {w.message}")
                            if w.code_reference: st.caption(f"  📖 Ref: {w.code_reference}")
                        elif w.severity == ModificationSeverity.WARNING:
                            st.warning(f"⚠️ **WARNING:** {w.message}")
                            if w.code_reference: st.caption(f"  📖 Ref: {w.code_reference}")
                        else:
                            st.info(f"ℹ️ {w.message}")
                    if val.can_proceed:
                        if st.button("✅ Confirm Removal", key="confirm_remove_btn", type="primary"):
                            editor = st.session_state['remove_editor']
                            new_result = editor.remove_column(remove_col_id)
                            st.session_state['editor_placement'] = new_result
                            gm.columns = []
                            for col_data in new_result.columns:
                                from src.grid_manager import Column as GMColumn
                                gm_col = GMColumn(
                                    id=col_data.id, x=col_data.x * 0.001, y=col_data.y * 0.001,
                                    width_nb=col_data.width, depth_nb=col_data.depth,
                                    junction_type=col_data.junction_type.value, is_floating=col_data.is_floating,
                                    reinforcement_rule=col_data.reinforcement_rule.value, orientation_deg=col_data.orientation_deg,
                                    level=0, z_top=story_height
                                )
                                gm.columns.append(gm_col)
                            gm.columns = gm.stack_columns(gm.columns, num_stories, story_height)
                            st.session_state['gm'] = gm
                            del st.session_state['remove_validation']
                            del st.session_state['remove_editor']
                            st.success(f"Removed column {remove_col_id}. Layout now has {len(new_result.columns)} columns.")
                            st.rerun()
                    else:
                        st.error("❌ Removal blocked — address CRITICAL issues above before proceeding.")
            with edit_tab2:
                st.markdown("**Specify coordinates for a new column.** Coordinates are in millimeters (mm).")
                add_c1, add_c2 = st.columns(2)
                with add_c1:
                    add_x = st.number_input("X coordinate (mm)", value=0.0, step=100.0, key="add_col_x")
                with add_c2:
                    add_y = st.number_input("Y coordinate (mm)", value=0.0, step=100.0, key="add_col_y")
                if st.button("🔍 Validate Placement", key="validate_add_btn"):
                    editor = ColumnEditor(
                        placement=editor_placement, centerlines=st.session_state['editor_centerlines'],
                        building_envelope=st.session_state['editor_envelope'], seismic_zone=st.session_state['editor_seismic_zone'],
                        primary_x=st.session_state['editor_primary_x'], primary_y=st.session_state['editor_primary_y']
                    )
                    val_result = editor.validate_add_column(add_x, add_y)
                    st.session_state['add_validation'] = val_result
                    st.session_state['add_editor'] = editor
                if 'add_validation' in st.session_state:
                    val = st.session_state['add_validation']
                    for w in val.warnings:
                        if w.severity == ModificationSeverity.CRITICAL:
                            st.error(f"🚫 **CRITICAL:** {w.message}")
                        elif w.severity == ModificationSeverity.WARNING:
                            st.warning(f"⚠️ **WARNING:** {w.message}")
                        else:
                            st.info(f"ℹ️ {w.message}")
                    if val.can_proceed:
                        if st.button("✅ Confirm Addition", key="confirm_add_btn", type="primary"):
                            editor = st.session_state['add_editor']
                            new_result = editor.add_column(add_x, add_y)
                            st.session_state['editor_placement'] = new_result
                            gm.columns = []
                            for col_data in new_result.columns:
                                from src.grid_manager import Column as GMColumn
                                gm_col = GMColumn(
                                    id=col_data.id, x=col_data.x * 0.001, y=col_data.y * 0.001,
                                    width_nb=col_data.width, depth_nb=col_data.depth,
                                    junction_type=col_data.junction_type.value, is_floating=col_data.is_floating,
                                    reinforcement_rule=col_data.reinforcement_rule.value, orientation_deg=col_data.orientation_deg,
                                    level=0, z_top=story_height
                                )
                                gm.columns.append(gm_col)
                            gm.columns = gm.stack_columns(gm.columns, num_stories, story_height)
                            st.session_state['gm'] = gm
                            del st.session_state['add_validation']
                            del st.session_state['add_editor']
                            st.success(f"Added new column. Layout now has {len(new_result.columns)} columns.")
                            st.rerun()

else:
    st.info("Adjust parameters in the sidebar and click 'Run Analysis' to generate the structure.")

st.markdown("---")
st.caption("StructOptima v1.0.0 · IS 456:2000 · IS 1893:2016 · IS 13920:2016")
