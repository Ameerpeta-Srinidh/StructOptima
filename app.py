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
<div style="background: linear-gradient(135deg, #1a237e 0%, #0d47a1 40%, #01579b 100%);
            padding: 40px 30px 30px 30px; border-radius: 12px; margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
    <h1 style="color: white; margin: 0 0 8px 0; font-size: 2.4em; letter-spacing: -0.5px;">
        🏗️ StructOptima
    </h1>
    <p style="color: rgba(255,255,255,0.92); font-size: 1.15em; margin: 0 0 18px 0; max-width: 700px;">
        Generate IS-code compliant structural designs from DXF files in minutes.
        Automated column placement, beam design, rebar detailing, and professional PDF reports.
    </p>
    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
        <span style="background: rgba(255,255,255,0.18); color: white; padding: 6px 16px;
                     border-radius: 20px; font-weight: 600; font-size: 0.95em;
                     border: 1px solid rgba(255,255,255,0.3);">
            IS 456:2000
        </span>
        <span style="background: rgba(255,255,255,0.18); color: white; padding: 6px 16px;
                     border-radius: 20px; font-weight: 600; font-size: 0.95em;
                     border: 1px solid rgba(255,255,255,0.3);">
            IS 1893:2016
        </span>
        <span style="background: rgba(255,255,255,0.18); color: white; padding: 6px 16px;
                     border-radius: 20px; font-weight: 600; font-size: 0.95em;
                     border: 1px solid rgba(255,255,255,0.3);">
            IS 13920:2016
        </span>
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

# ========== TRUST STATS BAR ==========
_ts1, _ts2, _ts3, _ts4 = st.columns(4)
_ts1.metric("Modules", "51", help="51 integrated structural design modules")
_ts2.metric("Test Suites", "28", help="28 automated test suites validating calculations")
_ts3.metric("IS 456 Compliant", "✓", help="Full compliance with IS 456:2000")
_ts4.metric("Indian Standard Codes", "4 Codes", help="IS 456 · IS 1893 · IS 13920 · IS 875")

st.markdown("---")

with st.expander("📐 DXF Input Guide — How to Prepare Your Architectural DXF", expanded=False):
    st.markdown("""
**StructOptima's universal parser handles almost any DXF format**, but for best results:

| Element | Recommended Format |
|---------|-------------------|
| **Walls** | `LINE` or `LWPOLYLINE` entities on a layer named `WALL`, `WALLS`, `A-WALL`, or similar |
| **Units** | Millimeters (mm) — this is the Indian standard |
| **Double walls** | Accepted! Both double-line walls (230mm offset) and single centerlines are auto-normalized |
| **Layer names** | Put walls on layers containing keywords: `WALL`, `STRUCT`, `BOUNDARY`, `ARCH` |
| **No layers?** | That's OK — the parser auto-detects wall geometry from line patterns |

**What NOT to include on wall layers:** Dimensions, text, furniture, annotations, hatches.

**Supported building shapes:** Rectangular, L-shape, C-shape, T-shape, H-shape, stepped, irregular.
    """)

# Design Assumptions & Safety Factors (Always visible)
with st.expander("Design Basis & Safety Factors (Click to expand)", expanded=False):
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("""
        **Design Code:** IS 456:2000 (Plain & Reinforced Concrete)
        
        **Units Used:**
        - Dimensions: **meters (m)**
        - Loads: **kN, kN/m, kN/m²**
        - Stress: **MPa (N/mm²)**
        - Rebar: **mm diameter**
        
        **Load Factors (Limit State):**
        - Dead Load: **1.5**
        - Live Load: **1.5**
        - Combined: **1.5 (DL + LL)**
        """)
    
    with col_b:
        st.markdown("""
        **Material Safety Factors:**
        - Concrete (γc): **1.5**
        - Steel (γs): **1.15**
        
        **Key Assumptions:**
        - Short column (Le/r < 12)
        - Simply supported beams
        - Isolated square footings
        - Tributary area load distribution
        
        **Deflection Limit:** Span/250
        
        **Punching Shear:** 0.25√fck MPa
        """)
    
    st.warning("All designs must be verified by a licensed structural engineer before construction.")

# Sidebar Steps
with st.sidebar:
    # ========== BRANDING HEADER ==========
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 5px 0;">
        <h2 style="margin: 0; color: #1a237e;">🏗️ StructOptima</h2>
        <p style="margin: 2px 0; font-size: 0.85em; color: #666;">v1.0.0 · March 2026</p>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Built by **Charan Tej, Chandana, and Vamshi**")
    st.markdown(
        "[⭐ GitHub Repository](https://github.com/Ameerpeta-Srinidh/StructOptima)",
        unsafe_allow_html=True
    )
    st.caption("Automated IS-code structural design engine — from DXF to PDF report in minutes.")
    st.markdown("---")
    
    st.header("Project Details")
    project_name = st.text_input("Project Name", value="Untitled Project", help="Name for reports and exports")
    engineer_name = st.text_input("Structural Engineer", value="", help="Name of the responsible engineer")
    drawing_ref = st.text_input("Drawing Ref. No.", value="", help="Drawing or job reference number")
    project_date = st.date_input("Date")
    st.markdown("---")
    st.header("Project Parameters")
    
    input_mode = st.radio("Input Method", ["Manual Dimensions", "Import CAD (DXF)", "Import BIM (IFC)"])
    
    cad_file = None
    auto_frame = False
    width = 0.0
    length = 0.0
    
    if input_mode == "Import CAD (DXF)":
        cad_file = st.file_uploader("Upload DXF File", type=["dxf"])
        auto_frame = st.checkbox("Auto-Frame from Architecture (Walls)", help="Check this if your file has only walls and you want AI to place columns.")
        
        st.subheader("Vertical Stack")
        num_stories = st.number_input("Number of Stories", min_value=1, max_value=50, value=2)
        story_height = st.number_input("Story Height (m)", 2.4, 6.0, 3.0)
        
    elif input_mode == "Import BIM (IFC)":
        try:
            import ifcopenshell
            _ifc_available = True
        except ImportError:
            _ifc_available = False
        
        if _ifc_available:
            ifc_file = st.file_uploader("Upload IFC File", type=["ifc"])
            st.info("BIM Mode extracts exact Material & Geometry from IfcColumn/IfcBeam.")
        else:
            ifc_file = None
            st.error(
                "**IFC import requires `ifcopenshell`** which is not installed.\n\n"
                "Install it with: `pip install ifcopenshell`\n\n"
                "Note: ifcopenshell can be difficult to install on some platforms. "
                "See [ifcopenshell.org](https://ifcopenshell.org/) for installation guides."
            )
            st.stop()
        
    else:
        width = st.slider("Floor Width (m)", 6.0, 50.0, 18.0, 1.0)
        length = st.slider("Floor Length (m)", 6.0, 50.0, 12.0, 1.0)
        
        st.subheader("Vertical Stack")
        num_stories = st.number_input("Number of Stories", min_value=1, max_value=50, value=2)
        story_height = st.number_input("Story Height (m)", 2.4, 6.0, 3.0)
    
    st.subheader("Building Type (IS 875 Part 2)")
    building_type_name = st.selectbox(
        "Occupancy Type",
        list(BUILDING_TYPES.keys()),
        index=0,
        help="Select building occupancy to apply IS 875 Part 2 compliant floor loads"
    )
    
    # Get IS 875 compliant load parameters
    load_params = get_load_parameters(building_type_name)
    
    # Display load summary
    with st.expander("View Design Loads (IS 875 Part 2)"):
        st.markdown(f"**{load_params.description}**")
        st.markdown(f"""
        | Load Type | Value | Reference |
        |-----------|-------|-----------|  
        | Live Load (Floor) | **{load_params.live_load_floor_kn_m2} kN/m²** | IS 875 Part 2 |
        | Live Load (Corridor) | {load_params.live_load_corridor_kn_m2} kN/m² | IS 875 Part 2 |
        | Floor Finish | {load_params.floor_finish_kn_m2} kN/m² | IS 875 Part 1 |
        | Partitions | {load_params.partition_load_kn_m2} kN/m² | IS 875 Part 1 |
        | Services | {load_params.services_load_kn_m2} kN/m² | Assumed |
        | **Total Floor Load** | **{load_params.total_floor_load_kn_m2:.1f} kN/m²** | - |
        """)
    
    # Calculate combined floor load
    live_load = load_params.total_floor_load_kn_m2 + (25 * load_params.slab_thickness_mm / 1000)
    wall_load = st.number_input("Wall Load (kN/m)", 0.0, 50.0, 12.0, help="Load from brick/block walls on beams")
    sbc = st.number_input("SBC (kN/m²)", min_value=50.0, max_value=500.0, value=200.0, help="Safe Bearing Capacity of soil")
    
    st.subheader("Seismic Zone (IS 1893:2016)")
    seismic_zone = st.selectbox(
        "Zone",
        SEISMIC_ZONES,
        index=1,
        format_func=lambda x: ZONE_DESCRIPTIONS.get(x, x),
        help="Select seismic zone per IS 1893:2016"
    )
    if seismic_zone in ["III", "IV", "V"]:
        st.caption("Ductile detailing per IS 13920 will be checked")
        st.caption("Strong Column-Weak Beam verification enabled")
        
    st.subheader("Wind Zone (IS 875 Part 3)")
    wind_zone_idx = st.selectbox(
        "Zone",
        ["1", "2", "3", "4", "5", "6"],
        index=1,
        help="Select Wind Zone per IS 875 Part 3 (Zone 1=33m/s, Zone 6=55m/s)"
    )
    from src.wind_load import WindZone, TerrainCategory
    wind_zone = WindZone(wind_zone_idx)
    terrain_cat = st.selectbox(
        "Terrain Category",
        ["1", "2", "3", "4"],
        index=1,
        help="Category 2: Open terrain with scattered obstructions (typical)"
    )
    terrain_cat_enum = TerrainCategory(terrain_cat)
    
    st.subheader("Architectural Features")
    add_staircase = st.checkbox("Add Staircase (Central Void)")
    
    cant_dirs = []
    if input_mode == "Manual Dimensions":
        st.write("Cantilever Balconies (1.5m):")
        c_left = st.checkbox("Left")
        c_right = st.checkbox("Right")
        c_top = st.checkbox("Top (Back)")
        c_bot = st.checkbox("Bottom (Front)")
        
        if c_left: cant_dirs.append("left")
        if c_right: cant_dirs.append("right")
        if c_top: cant_dirs.append("top")
        if c_bot: cant_dirs.append("bottom")
    
    st.subheader("Design Settings")
    
    st.sidebar.markdown("### Engineering Assumptions")
    assume_fixed = st.sidebar.checkbox("Fixed Supports (Base)", value=True, help="Uncheck for Pinned supports (Conservative)")
    use_cracked = st.sidebar.checkbox("Cracked Sections (IS 1893)", value=True, help="Applies Stiffness Modifiers: 0.7Ig (Col), 0.35Ig (Beam)")
    st.sidebar.info(
        "**Basis of Design:**\n"
        "- IS 456:2000 (RC Design)\n"
        "- IS 1893:2016 (Seismic)\n"
        "- **Safety Factors:** γc=1.5, γs=1.15\n"
        "- **Uplift Check:** 0.9DL + 1.5WL\n"
        "- **Pattern Loading:** Inactive (Simplified)"
    )
    
    with st.expander("Advanced Configuration"):
        conc_grade = st.selectbox("Concrete Grade", ["M20", "M25", "M30"], index=1)
        
    st.subheader("Sustainability")
    use_fly_ash = st.checkbox("Use Green Concrete (Fly Ash/Slag)", help="Reduces embodied carbon by approx 33%")
    
    st.subheader("Cost Optimization")
    enable_optimization = st.checkbox(
        "Enable Cost Optimization",
        value=False,
        help="Optimize column sizes by floor while maintaining IS 456 safety"
    )
    if enable_optimization:
        st.caption("All IS 456 safety factors maintained")
        st.caption("Columns sized to actual load requirements")
    
    st.subheader("Visualization")
    view_mode = st.selectbox(
        "View Mode", 
        ["Engineering", "Architectural", "Deflection", "Utilization", "Load Path"],
        index=0,
        help="Deflection: Animated Deformations | Utilization: D/C Ratio | Load Path: Transfer Beams"
    )

    st.markdown("---")
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
        gm.optimize_column_sizes(concrete=m_grade, fy=415.0)
        gm.detail_columns(concrete=m_grade, fy=415.0)
        gm.detail_beams(beams)
        gm.detail_slabs()
        
        if add_staircase:
            gm.detail_staircase()
        
        project_bbs = generate_bbs_from_grid_manager(gm, beams, "Residential Project")
            
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
            
        quantifier = Quantifier()
        bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=use_fly_ash)
        
        from src.audit import StructuralAuditor
        auditor = StructuralAuditor(gm, all_beams, footings)
        audit_results = auditor.run_audit()

        sorted_cols = sorted(gm.columns, key=lambda c: (c.x, c.y, c.level))
        
        fck = int(conc_grade[1:])
        floor_area_m2 = gm.width_m * gm.length_m
        building_weight = bom.total_concrete_vol_m3 * 25 + bom.total_steel_weight_kg * 0.00981 + floor_area_m2 * num_stories * live_load

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
            floor_width=width,
            floor_length=length,
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

    render_project_header()
    
    # 4 metric cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Total Concrete", f"{bom.total_concrete_vol_m3:.2f} m³", icon="🏢")
    with c2:
        render_metric_card("Total Steel", f"{bom.total_steel_weight_kg:.0f} kg", icon="🔩")
    with c3:
        render_metric_card("Est. Cost", f"INR {bom.total_cost_inr:,.2f}", icon="💰")
    with c4:
        render_metric_card("Carbon Footprint", f"{bom.total_carbon_kg/1000.0:.2f} Tons", icon="🌱")
        
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
st.markdown("""
<div style="background: linear-gradient(135deg, #e8f5e9 0%, #e3f2fd 100%);
            padding: 20px; border-radius: 10px; border-left: 5px solid #1565c0;
            margin: 10px 0;">
    <h4 style="color: #1565c0; margin-top: 0;">🛡️ Responsible Use — Engineering Best Practice</h4>
    <p style="color: #37474f; font-size: 0.95em; margin-bottom: 10px;">
        StructOptima generates <strong>preliminary structural designs compliant with IS 456:2000, 
        IS 1893:2016, and IS 13920:2016</strong>. Like any design tool — including STAAD.Pro, ETABS, 
        and SAP2000 — all outputs require professional review before construction.
    </p>
    <ul style="color: #37474f; font-size: 0.9em; margin-bottom: 0; padding-left: 20px;">
        <li>✅ <strong>IS-code calculations</strong> are automated with safety factors γc=1.5, γs=1.15</li>
        <li>✅ <strong>51 integrated modules</strong> cover columns, beams, slabs, foundations, seismic, and rebar detailing</li>
        <li>✅ <strong>Independent audit checks</strong> verify every design against code limits</li>
        <li>📋 Final designs should be <strong>reviewed and sealed by a licensed Structural Engineer</strong> for construction</li>
        <li>📋 Site-specific geotechnical investigation is recommended before foundation construction</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; padding: 15px 0; color: #9e9e9e; font-size: 0.85em;">
    <p style="margin: 0;">© 2026 StructOptima — Built by Charan Tej, Chandana, and Vamshi</p>
    <p style="margin: 4px 0 0 0;">All calculations per IS 456:2000 · IS 1893:2016 · IS 13920:2016 | v1.0.0</p>
    <p style="margin: 4px 0 0 0;">
        <a href="/terms" style="color: #1565c0; text-decoration: none;">Terms of Service</a> · 
        <a href="/privacy" style="color: #1565c0; text-decoration: none;">Privacy Notice</a>
    </p>
</div>
""", unsafe_allow_html=True)
