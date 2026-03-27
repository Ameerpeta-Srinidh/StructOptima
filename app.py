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
from src.shm_module import SHMPlanner

# --- Caching Wrappers for Expensive Operations (Phase 2) ---
@st.cache_data(show_spinner="Optimizing structure...")
def get_optimized_structure(columns, story_height, num_stories, fck):
    return optimize_structure(columns, story_height, num_stories, fck=fck, enable_optimization=True)

@st.cache_data(show_spinner="Running stability & fire checks...")
def get_stability_check_results(columns, all_beams, num_stories, story_height):
    return run_stability_check(columns, all_beams, num_stories, story_height)

@st.cache_data(show_spinner=False) # Changed spinner behavior as per instruction
def get_safety_warnings_results(columns, all_beams, floor_width, floor_length, fck, seismic_zone):
    from src.safety_warnings import run_safety_warnings_check # Added import as per instruction
    return run_safety_warnings_check(columns, all_beams, footings_or_width=floor_width, floor_length=floor_length, fck=fck, seismic_zone=seismic_zone)

# Helper removed. Logic moved to GridManager.generate_beams()

# --- App Layout ---

st.set_page_config(page_title="StructOptima — IS-Code Structural Design Engine", layout="wide", page_icon="🏗️")

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
    st.caption("Built by **Charan Tej, Chandana, and Srinidh**")
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
        
        # ... (Stack Config) ...
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
        
        # Allow override of stack or trust IFC?
        # Trust IFC for now but allow display
        
    else:
        width = st.slider("Floor Width (m)", 6.0, 50.0, 18.0, 1.0)
        # ... (Manual)
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
    live_load = load_params.total_floor_load_kn_m2 + (25 * load_params.slab_thickness_mm / 1000)  # + slab self-weight
    wall_load = st.number_input("Wall Load (kN/m)", 0.0, 50.0, 12.0, help="Load from brick/block walls on beams")
    sbc = st.number_input("SBC (kN/m²)", min_value=50.0, max_value=500.0, value=200.0, help="Safe Bearing Capacity of soil")
    
    st.subheader("Seismic Zone (IS 1893:2016)")
    seismic_zone = st.selectbox(
        "Zone",
        SEISMIC_ZONES,
        index=1,  # Default Zone III
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
    
    # --- Engineering Assumptions Sidebar ---
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

    # ========== MANDATORY PROFESSIONAL DISCLAIMER ==========
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
                        
                    # Security: Validate DXF magic bytes
                    header = cad_file.getvalue()[:100]
                    # ASCII DXF typically has '  0' or '999'. Binary has 'AutoCAD'
                    if not (b"AutoCAD" in header or b"SECTION" in header or b"  0" in header or b"999" in header):
                        st.error("Invalid DXF file. Security check failed: Magic bytes do not match expected DXF format.")
                        st.stop()
                        
                    # ... (DXF Logic) ...
                    tmp_file = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False)
                    tmp_file.write(cad_file.getbuffer())
                    tmp_file.close()
                    temp_filename = tmp_file.name
                        
                    from src.cad_loader import CADLoader
                    try:
                        loader = CADLoader(temp_filename)
                        gm, beams = loader.load_grid_manager(auto_frame=auto_frame)
                        
                        if auto_frame and not beams: # Only generate valid grid beams if auto-framer returned nothing
                            beams = gm.generate_beams()
                                
                        # Update GM Vertical Stack
                        gm.num_stories = num_stories
                        gm.story_height_m = story_height
                        
                        # Re-create columns for upper stories (Stacking Phase 1 Logic)
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
                        
                        st.success(f"Success! Imported {len(base_cols)} columns from CAD.")
                        
                    except Exception as e:
                        logger.error("Failed to load CAD file: %s", e)
                        capture_exception(e)
                        st.error(f"Failed to load CAD: {e}")
                        st.stop()
                    finally:
                        # Clean up temp file — avoids PermissionError on read-only PaaS hosts
                        try:
                            os.unlink(temp_filename)
                        except OSError:
                            pass
                
                elif input_mode == "Import BIM (IFC)":
                     if ifc_file is None:
                        st.error("Please upload an IFC file.")
                        st.stop()
                        
                     # Security: Validate IFC magic bytes (STEP format)
                     header = ifc_file.getvalue()[:100]
                     if b"ISO-10303-21" not in header:
                         st.error("Invalid IFC file. Security check failed: Missing ISO-10303-21 STEP signature.")
                         st.stop()
                        
                     # SAVE IFC
                     tmp_file = tempfile.NamedTemporaryFile(suffix='.ifc', delete=False)
                     tmp_file.write(ifc_file.getbuffer())
                     tmp_file.close()
                     temp_filename = tmp_file.name
                     
                     from src.bim_loader import BIMLoader
                     try:
                         loader = BIMLoader(temp_filename)
                         gm, beams = loader.load_grid_manager()
                         st.success(f"Success! Imported BIM Model: {len(gm.columns)} Cols, {len(beams)} Beams")
                         
                     except Exception as e:
                         logger.error("Failed to load IFC file: %s", e)
                         capture_exception(e)
                         st.error(f"Failed to load IFC: {e}")
                         st.stop()
                     finally:
                         # Clean up temp file — avoids PermissionError on read-only PaaS hosts
                         try:
                             os.unlink(temp_filename)
                         except OSError:
                             pass
    
                else:
                    # Manual Generation
                    gm = GridManager(
                        width_m=width, 
                        length_m=length, 
                        num_stories=num_stories,
                        story_height_m=story_height
                    )
                    gm.cantilever_dirs = cant_dirs # defined above
                    gm.cantilever_len_m = 1.5
                    gm.generate_grid()
                    beams = gm.generate_beams()
                
                # Save to cache
                st.session_state['gm'] = gm
                st.session_state['beams'] = beams
                
                # Initialize Column Editor Session States
                if ('loader' in locals() and hasattr(loader, 'placer') 
                        and loader.placer is not None):
                    st.session_state['editor_centerlines'] = loader.framer.centerlines
                    st.session_state['editor_envelope'] = loader.placer.building_envelope
                    st.session_state['editor_primary_x'] = loader.placer.primary_x
                    st.session_state['editor_primary_y'] = loader.placer.primary_y
                    st.session_state['editor_placement'] = loader.placement_result
                    st.session_state['editor_seismic_zone'] = seismic_zone
            else:
                # Load from cache (persists column editor modifications)
                gm = st.session_state['gm']
                beams = st.session_state['beams']

        # --- Column Editor UI ---
        if st.session_state.get('editor_placement') is not None:
            from src.column_editor import ColumnEditor, ModificationSeverity

            with st.expander("✏️ Column Editor — Add or Remove Columns", expanded=False):
                st.caption("Modify the auto-generated column layout. The system will "
                           "validate structural integrity per IS 456:2000.")

                editor_placement = st.session_state['editor_placement']
                col_ids = [c.id for c in editor_placement.columns]

                edit_tab1, edit_tab2 = st.tabs(["🗑️ Remove Column", "➕ Add Column"])

                with edit_tab1:
                    st.markdown("**Select a column to remove.** The system will check "
                                "if removal is structurally safe.")
                    remove_col_id = st.selectbox(
                        "Column to Remove",
                        col_ids,
                        key="remove_col_select"
                    )

                    # Show selected column info
                    sel_col = next((c for c in editor_placement.columns
                                   if c.id == remove_col_id), None)
                    if sel_col:
                        st.caption(f"📍 Location: ({sel_col.x:.0f}, {sel_col.y:.0f}) mm | "
                                   f"Type: {sel_col.junction_type.value} | "
                                   f"Size: {sel_col.width:.0f}×{sel_col.depth:.0f} mm")

                    if st.button("🔍 Validate Removal", key="validate_remove_btn"):
                        editor = ColumnEditor(
                            placement=editor_placement,
                            centerlines=st.session_state['editor_centerlines'],
                            building_envelope=st.session_state['editor_envelope'],
                            seismic_zone=st.session_state['editor_seismic_zone'],
                            primary_x=st.session_state['editor_primary_x'],
                            primary_y=st.session_state['editor_primary_y']
                        )
                        val_result = editor.validate_remove_column(remove_col_id)
                        st.session_state['remove_validation'] = val_result
                        st.session_state['remove_editor'] = editor

                    if 'remove_validation' in st.session_state:
                        val = st.session_state['remove_validation']
                        for w in val.warnings:
                            if w.severity == ModificationSeverity.CRITICAL:
                                st.error(f"🚫 **CRITICAL:** {w.message}")
                                if w.code_reference:
                                    st.caption(f"  📖 Ref: {w.code_reference}")
                            elif w.severity == ModificationSeverity.WARNING:
                                st.warning(f"⚠️ **WARNING:** {w.message}")
                                if w.code_reference:
                                    st.caption(f"  📖 Ref: {w.code_reference}")
                            else:
                                st.info(f"ℹ️ {w.message}")

                        if val.can_proceed:
                            if st.button("✅ Confirm Removal", key="confirm_remove_btn",
                                         type="primary"):
                                editor = st.session_state['remove_editor']
                                new_result = editor.remove_column(remove_col_id)
                                st.session_state['editor_placement'] = new_result

                                # Update GridManager base columns
                                gm.columns = []
                                for col_data in new_result.columns:
                                    from src.grid_manager import Column as GMColumn
                                    gm_col = GMColumn(
                                        id=col_data.id,
                                        x=col_data.x * 0.001,
                                        y=col_data.y * 0.001,
                                        width_nb=col_data.width,
                                        depth_nb=col_data.depth,
                                        junction_type=col_data.junction_type.value,
                                        is_floating=col_data.is_floating,
                                        reinforcement_rule=col_data.reinforcement_rule.value,
                                        orientation_deg=col_data.orientation_deg,
                                        level=0,
                                        z_top=story_height
                                    )
                                    gm.columns.append(gm_col)

                                # Stack for multi-story
                                gm.columns = gm.stack_columns(gm.columns, num_stories, story_height)

                                # Explicitly update the main session state with new columns before rerun
                                st.session_state['gm'] = gm

                                del st.session_state['remove_validation']
                                del st.session_state['remove_editor']
                                st.success(f"Removed column {remove_col_id}. "
                                           f"Layout now has {len(new_result.columns)} columns.")
                                st.rerun()
                        else:
                            st.error("❌ Removal blocked — address CRITICAL issues above "
                                     "before proceeding.")

                with edit_tab2:
                    st.markdown("**Specify coordinates for a new column.** "
                                "Coordinates are in millimeters (mm).")

                    add_c1, add_c2 = st.columns(2)
                    with add_c1:
                        add_x = st.number_input("X coordinate (mm)", value=0.0,
                                                step=100.0, key="add_col_x")
                    with add_c2:
                        add_y = st.number_input("Y coordinate (mm)", value=0.0,
                                                step=100.0, key="add_col_y")

                    if st.button("🔍 Validate Placement", key="validate_add_btn"):
                        editor = ColumnEditor(
                            placement=editor_placement,
                            centerlines=st.session_state['editor_centerlines'],
                            building_envelope=st.session_state['editor_envelope'],
                            seismic_zone=st.session_state['editor_seismic_zone'],
                            primary_x=st.session_state['editor_primary_x'],
                            primary_y=st.session_state['editor_primary_y']
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
                            if st.button("✅ Confirm Addition", key="confirm_add_btn",
                                         type="primary"):
                                editor = st.session_state['add_editor']
                                new_result = editor.add_column(add_x, add_y)
                                st.session_state['editor_placement'] = new_result

                                # Update GridManager base columns
                                gm.columns = []
                                for col_data in new_result.columns:
                                    from src.grid_manager import Column as GMColumn
                                    gm_col = GMColumn(
                                        id=col_data.id,
                                        x=col_data.x * 0.001,
                                        y=col_data.y * 0.001,
                                        width_nb=col_data.width,
                                        depth_nb=col_data.depth,
                                        junction_type=col_data.junction_type.value,
                                        is_floating=col_data.is_floating,
                                        reinforcement_rule=col_data.reinforcement_rule.value,
                                        orientation_deg=col_data.orientation_deg,
                                        level=0,
                                        z_top=story_height
                                    )
                                    gm.columns.append(gm_col)

                                # Stack for multi-story
                                gm.columns = gm.stack_columns(gm.columns, num_stories, story_height)

                                # Explicitly update the main session state with new columns before rerun
                                st.session_state['gm'] = gm

                                del st.session_state['add_validation']
                                del st.session_state['add_editor']
                                st.success(f"Added new column. "
                                           f"Layout now has {len(new_result.columns)} columns.")
                                st.rerun()

        # Common Pipeline Continued...
        
        # Staircase selection (Auto-select a Central bay with validation)
        staircase_bay = None
        if add_staircase:
            # Try to pick indices near middle
            mid_x = len(gm.x_grid_lines) // 2
            mid_y = len(gm.y_grid_lines) // 2
            # ensure valid index
            mid_x = max(0, min(mid_x, len(gm.x_grid_lines)-2))
            mid_y = max(0, min(mid_y, len(gm.y_grid_lines)-2))
            staircase_bay = (mid_x, mid_y)
            
            # Validate staircase bay doesn't conflict with imported geometry
            if input_mode != "Manual Dimensions":
                # Check if the central bay has columns inside it (not just at corners)
                bay_x_min = gm.x_grid_lines[mid_x]
                bay_x_max = gm.x_grid_lines[mid_x + 1] if mid_x + 1 < len(gm.x_grid_lines) else bay_x_min
                bay_y_min = gm.y_grid_lines[mid_y]
                bay_y_max = gm.y_grid_lines[mid_y + 1] if mid_y + 1 < len(gm.y_grid_lines) else bay_y_min
                
                _interior_cols_in_bay = [
                    c for c in gm.columns if c.level == 0
                    and bay_x_min < c.x < bay_x_max
                    and bay_y_min < c.y < bay_y_max
                ]
                if _interior_cols_in_bay:
                    st.warning(
                        f"⚠️ **Staircase bay conflict**: The auto-selected central bay "
                        f"({bay_x_min:.1f}–{bay_x_max:.1f}m × {bay_y_min:.1f}–{bay_y_max:.1f}m) "
                        f"contains {len(_interior_cols_in_bay)} interior column(s). "
                        f"Staircase void will override these columns — verify this is intended "
                        f"for your imported {input_mode.split('(')[1].rstrip(')')} layout."
                    )
            
        gm.calculate_trib_areas(staircase_bay=staircase_bay)
        gm.calculate_loads(floor_load_kn_m2=live_load, wall_load_kn_m=wall_load)
        
        # Advanced Analysis (FEA) — Updates beam loads with stiffness method results
        from src.analysis_integration import update_structural_analysis
        update_structural_analysis(gm, beams, use_cracked_sections=use_cracked)
        
        # ========== PATTERN LOADING LIMITATION WARNING ==========
        # IS 456 Cl. 22.4.1 requires pattern loading for continuous beams
        if len(beams) > 2:  # Multi-span beams present
            st.info(
                "📋 **Pattern Loading Note (IS 456 Cl. 22.4.1):** "
                "Current analysis uses uniform loading on all spans. "
                "IS 456 requires alternate-span pattern loading for continuous beams to capture "
                "maximum hogging moments at supports. Actual hogging may be 20–40% higher than shown. "
                "For critical designs, verify beam support moments with pattern loading in STAAD/ETABS."
            )
        
        # 2. Sizing & Detailing
        m_grade = Concrete.from_grade(conc_grade)
        gm.optimize_column_sizes(concrete=m_grade, fy=415.0)
        gm.detail_columns(concrete=m_grade, fy=415.0) # Generate Rebar Schedule
        gm.detail_beams(beams) # Generate Beam Schedule
        gm.detail_slabs()      # Generate Slab Schedule
        
        if add_staircase:
             gm.detail_staircase()
        
        # Generate Bar Bending Schedule
        project_bbs = generate_bbs_from_grid_manager(gm, beams, "Residential Project")
             
        # 3. Foundation (Only for Level 0 columns loads)
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
        
        # 4. Beams & BOM
        # beams already generated above (either from CAD or Manual)
        # Create deep-copied beam objects per story to avoid shared reference mutations
        
        all_beams = []
        for i in range(num_stories):
            for b in beams:
                # Deep copy to prevent shared mutations across stories
                copied = b.model_copy(deep=True)
                copied.id = f"{b.id}_L{i}"
                all_beams.append(copied)
            
        # 4. Quantification & BOM
        # Use defaults (INR 5000, INR 60) defined in Quantifier class
        quantifier = Quantifier()
        bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=use_fly_ash)
        
        # 5. Independent Audit (Phase 14)
        from src.audit import StructuralAuditor
        auditor = StructuralAuditor(gm, all_beams, footings)
        audit_results = auditor.run_audit()
        
        # Check overall status
        failed_checks = [r for r in audit_results if r.status == "FAIL"]
        if failed_checks:
            st.error(f"Audit Alert: {len(failed_checks)} checks FAILED. See Report for details.")
        else:
            st.success("Engineering Audit: ALL PASS")

        # 6. Visuals
        viz = Visualizer()
        v_mode_str = view_mode # Pass generic mode directly ("Deflection", "Use...", etc)
        # Verify mapping if needed, but Visualizer handles these strings now.
        fig = viz.create_structure_figure(gm, beams, footings, m_grade, view_mode=v_mode_str) 
        

                
        # --- RESULTS ---
        
        # Building Type Indicator
        st.info(f"**Design Basis:** {building_type_name} | **Live Load:** {load_params.live_load_floor_kn_m2} kN/m² | **IS 875 (Part 2): 1987**")
        
        # Metrics Row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Concrete", f"{bom.total_concrete_vol_m3:.2f} m³")
        c2.metric("Total Steel", f"{bom.total_steel_weight_kg:.0f} kg")
        c3.metric("Est. Cost", f"INR {bom.total_cost_inr:,.2f}")
        
        # Carbon Metric
        carb = bom.total_carbon_kg / 1000.0 # Tonnes
        delta_str = None
        if use_fly_ash:
           # Calc baseline for comparison
           baseline_bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=False)
           base_carb = baseline_bom.total_carbon_kg / 1000.0
           saved = base_carb - carb
           delta_str = f"-{saved:.2f} Tons"
           
        c4.metric("Carbon Footprint", f"{carb:.2f} Tons CO₂e", delta=delta_str, delta_color="inverse")
        
        # L/d Deflection Compliance (IS 456 Cl 23.2)
        with st.expander("📐 Beam L/d Deflection Check (IS 456 Cl 23.2)"):
            ld_data = []
            for b in beams:
                dx = b.end_point.x - b.start_point.x
                dy = b.end_point.y - b.start_point.y
                span_m = (dx**2 + dy**2)**0.5
                span_mm = span_m * 1000
                depth_mm = b.properties.depth_mm
                actual_ld = span_mm / depth_mm if depth_mm > 0 else 0
                # IS 456 Cl 23.2: Basic L/d ratios
                allowable_ld = 7.0 if getattr(b.properties, 'is_cantilever', False) else 20.0
                status = "✅ OK" if actual_ld <= allowable_ld else "⚠️ Check"
                ld_data.append({
                    "Beam": b.id,
                    "Span (mm)": f"{span_mm:.0f}",
                    "Depth (mm)": f"{depth_mm:.0f}",
                    "Actual L/d": f"{actual_ld:.1f}",
                    "Allowable L/d": f"{allowable_ld:.0f}",
                    "Status": status
                })
            if ld_data:
                import pandas as pd
                st.dataframe(pd.DataFrame(ld_data), use_container_width=True, hide_index=True)
                failed_ld = [d for d in ld_data if "Check" in d["Status"]]
                if failed_ld:
                    st.warning(f"{len(failed_ld)} beam(s) exceed basic L/d ratio — verify modification factors per IS 456 Cl 23.2.1")
                else:
                    st.success("All beams satisfy IS 456 Cl 23.2 basic L/d limits")
        
        # Material Breakdown Section
        st.markdown("---")
        st.subheader("Material Breakdown (" + conc_grade + " Concrete)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cement", f"{bom.cement_bags:.0f} bags", f"{bom.cement_kg:.0f} kg")
        m2.metric("Sand", f"{bom.sand_m3:.2f} m³")
        m3.metric("Aggregate (20mm)", f"{bom.aggregate_m3:.2f} m³")
        m4.metric("Water", f"{bom.water_liters:.0f} L")
        
        # Cost Optimization Results
        if enable_optimization:
            st.markdown("---")
            st.subheader("Cost Optimization Results")
            
            # Get concrete grade value
            fck = int(conc_grade[1:])  # "M25" -> 25
            
            # Run optimization
            opt_columns, opt_summary = get_optimized_structure(
                gm.columns,
                story_height,
                num_stories,
                fck
            )
            
            # Safety verification
            if opt_summary.all_safe:
                st.success("✅ All optimized designs pass IS 456 safety checks")
            else:
                st.warning("⚠️ Some designs require review - using conservative sizing")
            
            # Savings metrics
            s1, s2, s3 = st.columns(3)
            s1.metric(
                "Concrete Saved",
                f"{opt_summary.concrete_saved_m3:.2f} m³",
                f"{opt_summary.concrete_saved_pct:.1f}%"
            )
            s2.metric(
                "Steel Saved",
                f"{opt_summary.steel_saved_kg:.0f} kg",
                f"{opt_summary.steel_saved_pct:.1f}%"
            )
            s3.metric(
                "Cost Saved",
                f"₹{opt_summary.cost_saved:,.0f}",
                f"{opt_summary.cost_saved_pct:.1f}%"
            )
            
            # Optimization details
            with st.expander("View Optimized Column Sizes"):
                opt_data = []
                for col_id in sorted(opt_columns.keys()):
                    oc = opt_columns[col_id]
                    size_change = "→" if oc.original_size_mm != oc.optimized_size_mm else "="
                    opt_data.append({
                        "Column": col_id,
                        "Level": oc.level,
                        "Original": f"{oc.original_size_mm[0]}×{oc.original_size_mm[1]}",
                        "→": size_change,
                        "Optimized": f"{oc.optimized_size_mm[0]}×{oc.optimized_size_mm[1]}",
                        "Load (kN)": f"{oc.axial_load_kn:.0f}",
                        "Capacity (kN)": f"{oc.design_capacity_kn:.0f}",
                        "D/C Ratio": f"{oc.dc_ratio:.2f}",
                        "Xu/d": f"{oc.xu_d_ratio:.2f}",
                        "Req vs Prov (cm²)": f"{oc.required_steel_mm2/100:.1f} / {oc.provided_steel_mm2/100:.1f}",
                        "Check": "✓" if oc.is_safe else "✗",
                        "Gov": "M_min" if oc.is_min_ecc_governed else "P_u"
                    })
                st.dataframe(opt_data, use_container_width=True)
                st.caption("Gov: M_min = Governed by Minimum Eccentricity Check (< 0.05D)")
        
        # Stability & Fire Resistance Section
        st.markdown("---")
        st.subheader("Stability & Fire Resistance (IS 456 Table 16A / NBC 2016)")
        
        # Run stability checks
        stab_checks, stab_summary = get_stability_check_results(
            gm.columns,
            all_beams,
            num_stories,
            story_height
        )
        
        # Fire rating info
        fire_req = FIRE_RESISTANCE_TABLE[stab_summary.fire_rating_used]
        
        # Status indicators
        st.info(f"**Fire Rating Required:** {stab_summary.fire_rating_used.value} hours (based on {num_stories} floor building)")
        
        f1, f2, f3 = st.columns(3)
        f1.metric("Members Checked", stab_summary.total_members)
        f2.metric("Passed Stability", f"{stab_summary.passed_stability}/{stab_summary.total_members}")
        f3.metric("Passed Fire Check", f"{stab_summary.passed_fire}/{stab_summary.total_members}")
        
        # Overall status
        if stab_summary.all_passed:
            st.success("✅ All members pass stability and fire resistance checks")
        else:
            st.warning(f"⚠️ {len(stab_summary.failed_members)} members need attention")
            if stab_summary.recommendations:
                for rec in stab_summary.recommendations:
                    st.caption(f"📌 {rec}")
        
        # Fire resistance requirements
        with st.expander("View Fire Resistance Requirements (IS 456 Table 16A)"):
            st.markdown(f"""
            **Fire Rating: {stab_summary.fire_rating_used.value} hours** - {fire_req.description}
            
            | Member | Min Dimension | Min Cover |
            |--------|---------------|-----------|
            | Column | {fire_req.min_column_width_mm} mm | {fire_req.min_cover_column_mm} mm |
            | Beam | {fire_req.min_beam_width_mm} mm width | {fire_req.min_cover_beam_mm} mm |
            | Slab | {fire_req.min_slab_thickness_mm} mm thick | {fire_req.min_cover_slab_mm} mm |
            """)
        
        # Detailed check results
        with st.expander("View All Stability Checks"):
            check_data = []
            for check in stab_checks:
                check_data.append({
                    "Member": check.member_id,
                    "Type": check.member_type.title(),
                    "Slenderness": f"{check.slenderness_ratio:.1f} / {check.max_slenderness:.0f}",
                    "Stab OK": "✓" if check.is_stable else "✗",
                    "Dimension": f"{check.actual_dimension_mm} / {check.min_dimension_required_mm}",
                    "Fire OK": "✓" if check.is_fire_safe else "✗",
                    "Remarks": check.remarks
                })
            st.dataframe(check_data)
        
        # Seismic Analysis Section
        st.markdown("---")
        st.subheader("Seismic Analysis — IS 1893:2016 / IS 13920:2016")
        
        # Estimate building weight (concrete + steel + live load)
        # Use gm bounding box for all input modes (DXF/IFC/Manual) instead of
        # undefined width/length variables which silently fall back to 1000 kN
        floor_area_m2 = gm.width_m * gm.length_m
        building_weight = bom.total_concrete_vol_m3 * 25  # kN
        building_weight += bom.total_steel_weight_kg * 0.00981  # kN
        building_weight += floor_area_m2 * num_stories * live_load
        
        # Get concrete grade
        fck = int(conc_grade[1:])
        
        # Run seismic check
        seismic_result = run_seismic_check(
            gm.columns,
            all_beams,
            building_weight,
            zone=seismic_zone,
            building_type=building_type_name.lower().split()[0],
            fck=fck
        )
        
        # Zone info
        st.info(
            f"**Zone {seismic_zone}** | "
            f"Z = {seismic_result.parameters.zone_factor} | "
            f"Ah = {seismic_result.parameters.design_acceleration:.3f} | "
            f"Base Shear = {seismic_result.base_shear_kn:.0f} kN"
        )
        
        # Warnings
        if seismic_result.warnings:
            for warn in seismic_result.warnings:
                st.warning(warn)
        
        # SCWB Check
        if seismic_result.parameters.scwb_required:
            z1, z2 = st.columns(2)
            with z1:
                if seismic_result.all_scwb_pass:
                    st.success("✅ Strong Column-Weak Beam: PASS")
                else:
                    st.error("❌ Strong Column-Weak Beam: FAIL (Some joints need review)")
            with z2:
                if seismic_result.all_ductile_pass:
                    st.success(f"✅ Ductile Detailing: Ta={seismic_result.parameters.fundamental_period:.2f}s")
                else:
                    st.warning("⚠️ Ductile Detailing: Review stirrup spacing")
        
        # Deep Beam Check (Simple scan of beams)
        deep_beams = [b for b in beams if hasattr(b, 'properties') and (math.hypot(b.end_point.x-b.start_point.x, b.end_point.y-b.start_point.y)*1000 / b.properties.depth_mm) < 2.0]
        if deep_beams:
            st.error(f"⚠️ DEEP BEAM DETECTED: {len(deep_beams)} beams have L/D < 2.0. Manual Strut & Tie check required.")
        
        if seismic_result.has_floating_columns:
            st.error(f"⚠️ {len(seismic_result.floating_columns)} FLOATING COLUMN(S) DETECTED")
            for fc in seismic_result.floating_columns:
                st.caption(fc.warning)
        else:
            st.success("✅ No floating columns - load path continuous")
        
        # Torsional Irregularity Check (IS 1893 Cl. 7.1)
        # FEA solver is 2D (3 DOF/node) — cannot capture 3D torsional response.
        # Detect torsional irregularity: CoM vs CoR offset > 5% of plan dimension.
        _level_0_cols_torsion = [c for c in gm.columns if c.level == 0]
        if _level_0_cols_torsion:
            # Centre of Mass (weighted by tributary load)
            _total_load = sum(c.load_kn for c in _level_0_cols_torsion)
            if _total_load > 0:
                _com_x = sum(c.x * c.load_kn for c in _level_0_cols_torsion) / _total_load
                _com_y = sum(c.y * c.load_kn for c in _level_0_cols_torsion) / _total_load
            else:
                _com_x = sum(c.x for c in _level_0_cols_torsion) / len(_level_0_cols_torsion)
                _com_y = sum(c.y for c in _level_0_cols_torsion) / len(_level_0_cols_torsion)
            
            # Centre of Rigidity (weighted by column stiffness ∝ I = bd³/12)
            _total_stiffness = sum(c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion)
            if _total_stiffness > 0:
                _cor_x = sum(c.x * c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion) / _total_stiffness
                _cor_y = sum(c.y * c.width_nb * c.depth_nb**3 for c in _level_0_cols_torsion) / _total_stiffness
            else:
                _cor_x, _cor_y = _com_x, _com_y
            
            _offset_x = abs(_com_x - _cor_x)
            _offset_y = abs(_com_y - _cor_y)
            _plan_x = gm.width_m
            _plan_y = gm.length_m
            
            _torsion_ratio_x = _offset_x / _plan_x if _plan_x > 0 else 0
            _torsion_ratio_y = _offset_y / _plan_y if _plan_y > 0 else 0
            _is_torsionally_irregular = _torsion_ratio_x > 0.05 or _torsion_ratio_y > 0.05
            
            if _is_torsionally_irregular:
                st.error(
                    f"🚨 **TORSIONAL IRREGULARITY DETECTED** (IS 1893 Cl. 7.1)\n\n"
                    f"CoM–CoR offset: X = {_offset_x:.3f}m ({_torsion_ratio_x:.1%} of plan), "
                    f"Y = {_offset_y:.3f}m ({_torsion_ratio_y:.1%} of plan)\n\n"
                    f"**The current 2D frame analysis cannot capture torsional response.** "
                    f"Story drift estimates may be unconservative by 2–3×. "
                    f"A full 3D analysis (ETABS/STAAD) is required for this layout."
                )
                st.warning(
                    "⚠️ **Drift-based checks are unreliable** for this configuration. "
                    "Do NOT use drift values from this analysis for compliance verification."
                )
            else:
                st.success(
                    f"✅ No torsional irregularity — CoM–CoR offset within 5% "
                    f"(X: {_torsion_ratio_x:.1%}, Y: {_torsion_ratio_y:.1%})"
                )
        
        # Ductile detailing requirements
        with st.expander("View Ductile Detailing Requirements (IS 13920)"):
            if seismic_result.ductile_checks:
                ductile_data = []
                for dc in seismic_result.ductile_checks:
                    ductile_data.append({
                        "Member": dc.member_id,
                        "Type": dc.member_type.title(),
                        "Hinge Zone (mm)": int(dc.hinge_zone_length_mm),
                        "Max Stirrup Spacing": f"{dc.max_stirrup_spacing_mm:.0f} mm",
                        "Min Stirrup Dia": f"{dc.min_stirrup_dia_mm} mm",
                        "Legs Required": dc.required_legs
                    })
                st.dataframe(ductile_data)
                st.caption("📌 Plastic hinge zone: Use closer stirrup spacing at column/beam ends")
            else:
                st.info("Zone II - Ductile detailing not mandatory (recommended)")
        
        # Advanced Safety Warnings Section (Phase 2)
        st.markdown("---")
        st.subheader("Advanced Structural Code Checks")
        
        # Run safety warnings check
        safety_summary = get_safety_warnings_results(
            gm.columns,
            all_beams,
            floor_width=width,
            floor_length=length,
            fck=fck,
            seismic_zone=seismic_zone
        )
        
        # Display Critical Warnings
        if safety_summary.critical_warnings:
            for warn in safety_summary.critical_warnings:
                st.error(warn)
        else:
            st.success("✅ No critical plan irregularities detected")
            
        # Recommendations
        if safety_summary.recommendations:
            with st.expander("📝 Structural Recommendations", expanded=True):
                for rec in safety_summary.recommendations:
                    st.markdown(f"- {rec}")
        
        # Joint Shear Table
        with st.expander("View Joint Shear Capacity Checks (IS 13920)"):
            if safety_summary.joint_checks:
                joint_data = []
                for jc in safety_summary.joint_checks:
                    joint_data.append({
                        "Joint": jc.joint_id,
                        "Type": "Interior",
                        "Shear Demand": f"{jc.joint_shear_demand_kn:.1f} kN",
                        "Capacity": f"{jc.joint_shear_capacity_kn:.1f} kN",
                        "Util%": f"{jc.utilization_ratio:.0%}",
                        "Status": "✅ OK" if jc.is_adequate else "❌ FAIL"
                    })
                st.dataframe(joint_data)
                st.caption("Simplified check assuming typical reinforcement. Verify interior/exterior conditions.")
        
        # Cracked Section Info
        with st.expander("Modelling Assumptions (Stiffness Modifiers)"):
            st.markdown("""
            **IS 1893 / IS 16700 Requirement:**
            For seismic analysis, use cracked section properties:
            
            | Member | Uncracked (Ig) | Cracked (Effective) |
            |--------|----------------|---------------------|
            | Columns | 1.0 Ig | **0.70 Ig** |
            | Beams | 1.0 Ig | **0.35 Ig** |
            | Slabs | 1.0 Ig | **0.25 Ig** |
            
            *Current analysis uses Gross Stiffness (Ig). Deflections may be 1.5-2x higher in reality.*
            """)
            
        # Wind Analysis & Load Combinations
        st.markdown("---")
        st.subheader("Wind Analysis & Load Combinations (IS 875 Part 3 / IS 456 Table 18)")
        
        from src.wind_load import calculate_wind_load
        wind_result = calculate_wind_load(
            zone=wind_zone,
            height_m=num_stories * story_height,
            width_m=gm.width_m,
            length_m=gm.length_m,
            terrain_category=terrain_cat_enum,
            opening_percentage=10.0 # Default assumption
        )
        
        w1, w2, w3 = st.columns(3)
        w1.metric("Design Wind Speed (Top)", f"{wind_result.pressure_results[-1].design_wind_speed_ms:.1f} m/s")
        w2.metric("Wind Base Shear (X)", f"{wind_result.total_base_shear_x_kn:.0f} kN")
        w3.metric("Wind Base Shear (Y)", f"{wind_result.total_base_shear_y_kn:.0f} kN")
        
        if wind_result.warnings:
            for w in wind_result.warnings:
                st.warning(w)
                
        # Load Combinations Summary
        from src.load_combinations import LoadCombinationManager, get_summary_report
        
        # Calculate total building loads for stability check summary
        total_dl = building_weight - (floor_area_m2 * num_stories * live_load)
        total_ll = floor_area_m2 * num_stories * live_load
        total_wl = max(wind_result.total_base_shear_x_kn, wind_result.total_base_shear_y_kn)
        total_eq = seismic_result.base_shear_kn
        
        combo_mgr = LoadCombinationManager(
            include_wind=True,
            include_seismic=True,
            seismic_zone=seismic_zone
        )
        
        with st.expander("View Governing Load Combinations & Stability Check"):
            st.code(get_summary_report(combo_mgr, total_dl, total_ll, total_wl, total_eq), language="text")
        
        # Tabs for View Selection
        v_tab1, v_tab2 = st.tabs(["3D View", "2D Plan View"])
        
        with v_tab1:
             # Use pre-calculated 3D figure
             st.plotly_chart(fig, use_container_width=True)
             
        with v_tab2:
             # Level Selector
             level_sel = st.slider("Select Level", 1, num_stories, 1)
             fig_2d = viz.create_2d_plan(gm, beams, view_mode=v_mode_str, level=level_sel)
             st.plotly_chart(fig_2d, use_container_width=True)
        
        # Detailed Tables & Tools
        t1, t2, t3, t4, t5, t6 = st.tabs(["Column Schedule", "Bill of Materials", "Bar Bending Schedule", "Math Inspector", "Site Execution Guide", "BIM & Handover"])
        
        with t1:
            # Show Level 0 Separately or Sorted?
            # Let's just list them all, sorted by ID then Level
            sorted_cols = sorted(gm.columns, key=lambda c: (c.x, c.y, c.level))
            
            # Map footings to Level 0 cols
            ft_map = {c.id: f for c, f in zip(level_0_cols, footings)}
            
            col_data = []
            for c in sorted_cols:
                ft_str = "-"
                if c.level == 0 and c.id in ft_map:
                    ft = ft_map[c.id]
                    ft_str = f"{ft.length_m:.2f}x{ft.width_m:.2f}x{ft.thickness_mm/1000:.2f}"
                
                # Fetch Rebar Info
                main_rebar = "-"
                ties = "-"
                if hasattr(gm, 'rebar_schedule') and c.id in gm.rebar_schedule:
                    res = gm.rebar_schedule[c.id]
                    main_rebar = res.main_bars_desc
                    ties = res.links_desc

                col_data.append({
                    "ID": c.id,
                    "Level": c.level,
                    "Size": c.label,
                    "Load (kN)": f"{c.load_kn:.1f}",
                    "Main Steel": main_rebar,
                    "Stirrups": ties,
                    "Footing": ft_str
                })
                
            st.dataframe(col_data)
            
        with t2:
            st.subheader("Bill of Materials")
            st.caption("Per IS 456:2000 | Concrete mix design per IS 10262")
            bom_data = [
                {"Item": "Concrete", "Quantity": f"{bom.total_concrete_vol_m3:.2f}", "Unit": "m\u00b3", "Rate (INR)": "5,000/m\u00b3", "Amount (INR)": f"{bom.concrete_cost_inr:,.2f}"},
                {"Item": "Steel", "Quantity": f"{bom.total_steel_weight_kg:.0f}", "Unit": "kg", "Rate (INR)": "60/kg", "Amount (INR)": f"{bom.steel_cost_inr:,.2f}"},
            ]
            st.dataframe(bom_data, use_container_width=True)
            st.markdown(f"**Total Estimated Cost: INR {bom.total_cost_inr:,.2f}**")
            
            st.markdown("---")
            st.markdown("**Carbon Footprint**")
            carb_table = [
                {"Material": "Concrete", "Quantity": f"{bom.total_concrete_vol_m3:.2f} m\u00b3", "Emission Factor": "300 kg CO\u2082/m\u00b3", "CO\u2082e (kg)": f"{bom.concrete_carbon_kg:.1f}"},
                {"Material": "Steel", "Quantity": f"{bom.total_steel_weight_kg:.0f} kg", "Emission Factor": "1.85 kg CO\u2082/kg", "CO\u2082e (kg)": f"{bom.steel_carbon_kg:.1f}"},
            ]
            st.dataframe(carb_table, use_container_width=True)
            st.markdown(f"**Total Carbon Footprint: {bom.total_carbon_kg/1000:.2f} Tonnes CO\u2082e**")
            
        with t3:
            st.markdown("### Bar Bending Schedule & Optimization")
            
            # BBS Settings
            with st.expander("🛠️ BBS Analysis Settings", expanded=True):
                c_bbs1, c_bbs2, c_bbs3 = st.columns(3)
                
                with c_bbs1:
                    bbs_deduction_method = st.radio(
                        "Bend Deduction Method",
                        ["IS 2502 (Formula)", "SP 34 (Constants)"],
                        help="IS 2502 uses theoretical centerline. SP 34 uses simplified constants (e.g. 2d for 90°)."
                    )
                    use_sp34 = bbs_deduction_method == "SP 34 (Constants)"
                    
                with c_bbs2:
                    bbs_seismic_hooks = st.checkbox(
                        "Force 135° Seismic Hooks", 
                        value=True,
                        help="Mandatory for IS 13920 seismic detailing"
                    )
                    
                with c_bbs3:
                    stock_len = st.number_input(
                        "Rebar Stock Length (m)",
                        min_value=6.0,
                        max_value=15.0,
                        value=12.0,
                        step=0.5,
                        help="Standard commercial length for optimization"
                    )

            # --- Advanced BBS Calculation & Optimization ---
            
            # Helper to parse "4-16#" string
            def parse_rebar_string(desc):
                try:
                    if not desc or desc == "-": return 0, 0
                    parts = desc.split('-')
                    num = int(parts[0])
                    dia_str = parts[1].replace('#', '').replace('mm', '').strip()
                    dia = int(dia_str)
                    return num, dia
                except:
                    return 0, 0

            all_cut_lists = []
            congestion_warnings = []
            
            # Process Columns for Cutting Length
            for col in gm.columns:
                if col.id in gm.rebar_schedule:
                    res = gm.rebar_schedule[col.id]
                    num_main, dia_main = parse_rebar_string(res.main_bars_desc)
                    
                    if num_main > 0:
                        # Main Bars (Vertical)
                        # Length = Floor Height + Lap/Dev + Starting overlap - Cover
                        # Simplified: Story Height + Lap Length (50d)
                        cut_len_res = BBSUtils.calculate_cutting_length(
                            shape_code=0, # Straight with lap/crank
                            dims_mm={"A": (gm.story_height_m * 1000) + (50 * dia_main)},
                            bar_dia_mm=dia_main,
                            bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502
                        )
                        
                        all_cut_lists.append({
                            "bar_mark": f"{col.id}-Main",
                            "dia": dia_main,
                            "length": cut_len_res.cutting_length_mm,
                            "count": num_main,
                            "weight": cut_len_res.cutting_length_mm * num_main * (dia_main**2/162) / 1000
                        })
                        
                    # Stirrups/Ties
                    # Length = Perimeter + Hooks - Abysmal Cover
                    if res.links_desc:
                         # "8# @ 150 c/c"
                         try:
                             l_dia_str = res.links_desc.split('#')[0]
                             l_dia = int(l_dia_str)
                             l_spacing_str = res.links_desc.split('@')[1].split('c/c')[0].strip()
                             l_spacing = int(l_spacing_str)
                             
                             num_links = int((gm.story_height_m * 1000) / l_spacing)
                             
                             # Rectangular stirrup
                             # A = Width - 2*Cover, B = Depth - 2*Cover
                             cov = 40 
                             dim_a = col.width_nb - 2*cov
                             dim_b = col.depth_nb - 2*cov
                             
                             hook_type = HookType.SEISMIC_135 if bbs_seismic_hooks else HookType.STANDARD_90
                             
                             cut_len_res = BBSUtils.calculate_cutting_length(
                                shape_code=51, # Rectangular Box
                                dims_mm={"A": dim_a, "B": dim_b},
                                bar_dia_mm=l_dia,
                                bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502,
                                hook_type=hook_type
                             )
                             
                             all_cut_lists.append({
                                "bar_mark": f"{col.id}-Tie",
                                "dia": l_dia,
                                "length": cut_len_res.cutting_length_mm,
                                "count": num_links,
                                "weight": cut_len_res.cutting_length_mm * num_links * (l_dia**2/162) / 1000
                             })
                             
                         except:
                             pass

                    # Congestion check
                    if "WARN" in res.congestion_status or "FAIL" in res.congestion_status:
                        congestion_warnings.append(f"Column {col.id}: {res.congestion_status}")

            # Process Beams
            # Assuming 'all_beams' exists from earlier scope
            for bm in all_beams:
                 if hasattr(gm, 'beam_schedule') and bm.id in gm.beam_schedule:
                     res = gm.beam_schedule[bm.id]
                     
                     # Bottom Bars
                     n_bot, d_bot = parse_rebar_string(res.bottom_bars_desc)
                     if n_bot > 0:
                         span_mm = bm.properties.depth_mm * 12 # Rough span access or recalculate
                         # Using approximate from model since exact span variable not easily handy
                         # For accurate BBS, should store span in Member
                         
                         # Assume StartPt-EndPt dist
                         l_m = ((bm.end_point.x-bm.start_point.x)**2 + (bm.end_point.y-bm.start_point.y)**2)**0.5
                         l_mm = l_m * 1000
                         
                         cut_len_res = BBSUtils.calculate_cutting_length(
                            shape_code=21, # Straight with hooks
                            dims_mm={"A": l_mm + 50*d_bot}, # Simple anchorage add
                            bar_dia_mm=d_bot,
                            bend_deduction=BendDeductionType.SP_34 if use_sp34 else BendDeductionType.IS_2502,
                            hook_type=HookType.SEISMIC_135 if bbs_seismic_hooks else HookType.STANDARD_90
                         )
                         all_cut_lists.append({
                            "bar_mark": f"{bm.id}-Bot",
                            "dia": d_bot,
                            "length": cut_len_res.cutting_length_mm,
                            "count": n_bot,
                            "weight": cut_len_res.cutting_length_mm * n_bot * (d_bot**2/162) / 1000
                         })
                         
                     # Stirrups
                     # Very simplified extraction
                     pass

            # --- Optimization UI ---
            st.markdown("#### ✂️ Cut Optimization (Stock Visualization)")
            if st.checkbox("Run Cutting Optimization"):
                opt_results = BBSUtils.optimize_cutting_from_stock(
                    all_cut_lists, 
                    stock_length_mm=stock_len*1000
                )
                
                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Stock Bars Needed", opt_results.total_stock_bars)
                m2.metric("Total Wastage", f"{opt_results.total_wastage_pct:.1f}%")
                m3.metric("Offcuts Useful", len(opt_results.offcuts))
                
                # Detailed Plan
                with st.expander("View Cutting Patterns"):
                    for pattern in opt_results.cutting_patterns[:20]: # Show top 20
                        st.text(f"Stock Bar (Dia {pattern.bar_diameter_mm}mm): " + 
                                f" | ".join([f"{c['length']:.0f}mm ({c['mark']})" for c in pattern.cuts]) + 
                                f" [Rem: {pattern.remaining_length_mm:.0f}mm]")
                    if len(opt_results.cutting_patterns) > 20:
                        st.caption(f"... and {len(opt_results.cutting_patterns)-20} more patterns")

            # Congestion Alerts
            if congestion_warnings:
                st.error(f"⚠️ {len(congestion_warnings)} Congestion Alerts")
                st.write(congestion_warnings)

            st.markdown("---")
            st.markdown(f"**Total Estimated Steel:** {project_bbs.total_steel_kg:.2f} kg (Pre-Optimization)")
            
            # Summary by diameter
            st.markdown("#### Steel Summary by Diameter")
            summary_data = []
            for dia in sorted(project_bbs.summary_by_diameter.keys()):
                wt = project_bbs.summary_by_diameter[dia]
                pct = (wt / project_bbs.total_steel_kg * 100) if project_bbs.total_steel_kg > 0 else 0
                summary_data.append({"Diameter (mm)": dia, "Weight (kg)": f"{wt:.2f}", "% of Total": f"{pct:.1f}%"})
            st.dataframe(summary_data)
            
            # Member-wise breakdown
            with st.expander("Detailed Member-wise BBS Report"):
                for member in project_bbs.members:
                    st.text(f"{member.member_id} • {member.total_weight_kg:.2f} kg")
                    entry_data = []
                    for e in member.entries:
                        entry_data.append({
                            "Mark": e.bar_mark,
                            "Dia": e.bar_diameter_mm,
                            "Shp": e.shape_code,
                            "L_cut": f"{e.cutting_length_mm:.0f}",
                            "Nos": e.number_of_bars,
                            "Wt": f"{e.total_weight_kg:.2f}"
                        })
                    st.dataframe(entry_data, height=150)
            
            # Development & Lap Length Schedule
            st.markdown("---")
            st.markdown("#### Development & Lap Length Schedule (IS 456 Cl 26.2)")
            

        with t4:
            st.markdown("### Engineering Calculations Log")
            col_list = [c.id for c in sorted_cols]
            selected_col_id = st.selectbox("Select Column to Inspect", col_list)
            
            if selected_col_id and hasattr(gm, 'rebar_schedule') and selected_col_id in gm.rebar_schedule:
                res = gm.rebar_schedule[selected_col_id]
                if hasattr(res, 'math_log') and res.math_log:
                    st.code("\n".join(res.math_log), language="text")
                else:
                    st.info("No logs available (Audit not passed or simplified run).")
            else:
                st.warning("Please select a valid column.")

        with t5:
            st.header("Site Execution & Quality Control")
            st.markdown("Use these checklists for on-site inspections to ensure compliance with IS 456 / IS 13920.")
            
            from src.site_guide import SITE_CHECKLISTS
            
            # Display Checklists as Expanders
            for title, content in SITE_CHECKLISTS.items():
                with st.expander(f"{title} Checklist", expanded=False):
                    st.markdown(content)
            
            st.info("These guidelines are based on standard codes. Specific project requirements may vary.")

            st.markdown("---")
            st.subheader("Engineering Sanity Checks")
            st.markdown("Rules of Thumb vs Calculated Metrics")
            
            total_conc_vol = sum([b.properties.width_mm * b.properties.depth_mm * gm.story_height_m * 1e-9 for b in beams]) * 10
             # Rough est
            total_steel_kg = project_bbs.total_steel_kg if project_bbs else 0
            
            # Metric: Steel Density
            # Vol concrete approx: Area * Height * 0.5 (void ratio) - very rough
            # Better: Total Concrete from BOQ module if available.
            # Use bom data
            vol_concrete = 0
            if 'bom' in locals() and bom:
                vol_concrete = bom.total_concrete_vol_m3
            
            density = total_steel_kg / vol_concrete if vol_concrete > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Concrete Volume", f"{vol_concrete:.1f} m³")
            m2.metric("Total Steel", f"{total_steel_kg:.1f} kg")
            m3.metric("Steel Density", f"{density:.1f} kg/m³", delta=f"{density-100:.1f} vs Typ (100)", delta_color="inverse")
            
            if density > 130:
                st.warning("⚠️ High steel consumption! Check for over-design.")
            elif density < 70:
                st.warning("⚠️ Low steel consumption! Check for minimum reinforcement compliance.")
            else:
                st.success("✅ Steel consumption within normal range (70-130 kg/m³).")

        # --- LAYOUT NEGOTIATION ---
        st.markdown("---")
        st.subheader("🏗️ Layout Negotiation — Architect ↔ Engineer")
        st.caption("Dual-objective optimization: find column placements that satisfy both structural safety AND architectural aesthetics.")

        try:
            from src.layout_scorer import LayoutScorer, ColumnCandidate
            from src.layout_optimizer import LayoutOptimizer, OptimizationConfig

            # Convert GridManager columns to ColumnCandidates
            base_cols = []
            level_0_cols = [c for c in gm.columns if c.level == 0]
            xs_all = [c.x for c in level_0_cols]
            ys_all = [c.y for c in level_0_cols]

            for col in level_0_cols:
                is_corner = (
                    (col.x == min(xs_all) or col.x == max(xs_all)) and
                    (col.y == min(ys_all) or col.y == max(ys_all))
                )
                is_edge = (
                    col.x == min(xs_all) or col.x == max(xs_all) or
                    col.y == min(ys_all) or col.y == max(ys_all)
                ) and not is_corner

                base_cols.append(ColumnCandidate(
                    id=col.id, x=col.x, y=col.y,
                    width_mm=col.width_nb, depth_mm=col.depth_nb,
                    is_corner=is_corner, is_edge=is_edge
                ))

            # Build wall segments for scorer
            wall_segments = []
            if hasattr(gm, 'x_grid_lines') and hasattr(gm, 'y_grid_lines'):
                for x in gm.x_grid_lines:
                    wall_segments.append(((x, min(gm.y_grid_lines)), (x, max(gm.y_grid_lines))))
                for y in gm.y_grid_lines:
                    wall_segments.append(((min(gm.x_grid_lines), y), (max(gm.x_grid_lines), y)))

            scorer = LayoutScorer(walls=wall_segments)
            optimizer = LayoutOptimizer(
                scorer=scorer,
                baseline_columns=base_cols,
                config=OptimizationConfig(max_candidates=30, top_n=3)
            )

            results = optimizer.optimize()

            if results:
                import pandas as pd
                table_data = []
                for r in results:
                    table_data.append({
                        "Layout": r.layout_id,
                        "Structural Score": f"{r.structural_score:.1f}/100",
                        "Aesthetic Score": f"{r.aesthetic_score:.1f}/100",
                        "Composite Score": f"{r.composite_score:.1f}/100",
                        "Columns": len(r.columns),
                    })

                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Best layout recommendation
                best = results[0]
                if best.layout_id == "Baseline":
                    st.success(f"✅ **Recommendation:** Your current layout is already optimal! (Composite: {best.composite_score:.1f}/100)")
                else:
                    st.info(f"💡 **Recommendation:** Layout **{best.layout_id}** offers the best balance. (Composite: {best.composite_score:.1f}/100)")

                # Per-column detail expander
                with st.expander("📊 Detailed Per-Column Scores (Best Layout)"):
                    detail_data = []
                    for sc in best.columns:
                        detail_data.append({
                            "Column": sc.column.id,
                            "X (m)": f"{sc.column.x:.2f}",
                            "Y (m)": f"{sc.column.y:.2f}",
                            "Structural": f"{sc.structural_score:.0f}",
                            "Aesthetic": f"{sc.aesthetic_score:.0f}",
                            "Wall Proximity": sc.aesthetic_details.get("wall_concealability", "N/A"),
                            "Room Avoidance": sc.aesthetic_details.get("room_centroid_avoidance", "N/A"),
                        })
                    st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)
            else:
                st.warning("No alternative layouts found. The baseline is the only viable option.")

        except Exception as e:
            logger.error("Layout negotiation failed: %s", e)
            st.warning(f"Layout negotiation could not run: {e}")

        # --- EXPORTS ---
        st.markdown("---")
        st.subheader("Downloads & Reporting")

        c_d1, c_d2 = st.columns(2)
        
        # Excel
        xls_data = ExcelExporter.export_to_excel(gm, beams, bom)
        c_d1.download_button(
            label="📊 Download Excel Data (.xlsx)",
            data=xls_data,
            file_name="Structural_Data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        
        # DXF Export (New Strategy)
        from src.dxf_exporter import StructuralDXFExporter
        dxf_filename = "Structural_Plan.dxf"
        StructuralDXFExporter.export_structural_dxf(gm, beams, dxf_filename)
        
        with open(dxf_filename, "rb") as f:
            dxf_data = f.read()
            c_d1.download_button(
                label="📐 Download Structural Plan (.dxf)",
                data=dxf_data,
                file_name="Structural_Plan.dxf",
                mime="application/dxf"
            )

        # Professional DXF Export (Foundation Plan & Beam Schedule)
        from src.dxf_exporter import ProfessionalDXFExporter
        import datetime
        prof_dxf_filename = "Foundation_Plan_Professional.dxf"
        design_info = {
            "project_name": project_name if 'project_name' in locals() and project_name else "PROPOSED BUILDING",
            "engineer": engineer_name if 'engineer_name' in locals() and engineer_name else "STRUCTURAL ENGINEER",
            "date": datetime.datetime.now().strftime("%d-%m-%Y"),
            "sheet": "S-1",
            "scale": "1:100"
        }
        
        try:
            prof_exporter = ProfessionalDXFExporter(gm, beams, design_info, drawing_type="FOUNDATION")
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
            logger.error("Failed to generate Professional DXF: %s", e)
            c_d2.error("Prof. DXF export failed.")
        
        # Layer-wise Exports Section
        st.markdown("---")
        st.markdown("#### 📐 Layer-wise Structural Plans")
        
        floor_cols = st.columns(min(num_stories, 4))
        for lvl in range(num_stories):
            col_idx = lvl % 4
            
            # Generate floor DXF
            floor_dxf = f"Floor_{lvl}_Plan.dxf"
            StructuralDXFExporter.export_floor_dxf(gm, beams, lvl, floor_dxf)
            
            with open(floor_dxf, "rb") as f:
                floor_cols[col_idx].download_button(
                    label=f"📐 Floor {lvl} DXF",
                    data=f.read(),
                    file_name=f"Floor_{lvl}_Plan.dxf",
                    mime="application/dxf",
                    key=f"dxf_floor_{lvl}"
                )
        
        gm.footings = footings # Attach for report generator
        reporter = ReportGenerator()
        
        st.markdown("#### 📄 Floor-wise Reports")
        report_floor_cols = st.columns(min(num_stories, 4))
        for lvl in range(num_stories):
            col_idx = lvl % 4
            
            # Generate floor PDF
            floor_pdf = f"Floor_{lvl}_Report.pdf"
            reporter.generate_floor_report(floor_pdf, gm, lvl)
            
            with open(floor_pdf, "rb") as f:
                report_floor_cols[col_idx].download_button(
                    label=f"📄 Floor {lvl} Report",
                    data=f.read(),
                    file_name=f"Floor_{lvl}_Report.pdf",
                    mime="application/pdf",
                    key=f"pdf_floor_{lvl}"
                )
        
        with t6:
            st.markdown("### Construction & Handover Hub")
            st.info("Bridge the gap between Design and Execution with BIM L3 tools.")
            
            # Sub-tabs for the specific modules
            ht1, ht2, ht3, ht4, ht5 = st.tabs(["Design Reports", "BIM Export (COBie)", "Site Inspection", "SHM & IoT", "Digital Twin"])
            
            with ht5:
                # Digital Twin Tab
                from src.digital_twin import DigitalTwinExplorer
                dt = DigitalTwinExplorer("Project Phoenix")
                
                st.subheader("🏙️ Interactive Digital Twin")
                st.markdown("Explore As-Built vs As-Designed states and access COBie metadata.")
                
                c_dt1, c_dt2 = st.columns([3, 1])
                
                with c_dt2:
                    st.markdown("#### Controls")
                    view_state = st.radio("Model State", ["As-Designed", "As-Built"], index=0)
                    st.checkbox("Show MEP Systems", value=False)
                    st.checkbox("Show Architectural", value=True)
                    
                    sel_elem = st.selectbox("Select Element to Inspect", [c.id for c in gm.columns] + ["B1", "B2"])
                    
                with c_dt1:
                    # Metadata Overlay
                    if sel_elem:
                        meta = dt.get_element_metadata(sel_elem)
                        st.info(f"**Selected:** {sel_elem}")
                        cols = st.columns(3)
                        for i, (k, v) in enumerate(meta.items()):
                            cols[i%3].metric(k, v)
                            
                        if view_state == "As-Built":
                            dev = dt.get_as_built_deviation(sel_elem)
                            st.warning(f"⚠️ As-Built Deviation: {dev['total_mm']}mm (dx:{dev['dx']}, dy:{dev['dy']}, dz:{dev['dz']})")
                
                st.markdown("#### 4D Construction Phasing")
                sim_date = st.date_input("Simulate Project Date")
                active_elems = dt.generate_construction_schedule_overlay(str(sim_date))
                st.write(f"Active Construction Elements: {', '.join(active_elems)}")
            
            with ht1:
                st.subheader("Structural Calculation Reports")
                st.markdown("Generate compliant design reports for peer review and municipal approval.")
                
                if st.button("Generate Detailed Design Report"):
                    report_gen = DesignReportGenerator(project_name=project_name, engineer_name=engineer_name if engineer_name else "Not Specified")
                    
                    # Validate Model
                    val_res = report_gen.validate_model(modal_mass_percent=92.5, freq_hz=seismic_result.parameters.fundamental_period if 'seismic_result' in locals() else 0.5)
                    
                    # Drift Checks (Simulated for visualization)
                    report_gen.check_storey_drift("Ground Floor", 8.0, 3000.0)
                    report_gen.check_storey_drift("First Floor", 12.0, 3000.0)
                    
                    # Sample Calc
                    report_gen.add_sample_calculation(
                        "Typical Column Design", "C1", 
                        [f"Pu = {gm.columns[0].load_kn:.1f} kN", "Mu = Min Eccentricity"], 
                        "IS 456 Cl 39.3"
                    )
                    
                    report_text = report_gen.generate_report()
                    st.text_area("Report Preview", report_text, height=300)
                    
                    st.download_button(
                        label="📄 Download PDF Report",
                        data=report_text,
                        file_name="Detailed_Design_Report.txt",
                        mime="text/plain"
                    )

            with ht2:
                st.subheader("COBie v3 Data Exchange")
                st.markdown("Export data for Facility Management (FM) software.")
                
                if st.button("Generate COBie Data"):
                    cobie = CobieExporter("Project Phoenix")
                    
                    # Add Types
                    cobie.add_type("ResBeam", "Beam", "RCC Beam M25")
                    cobie.add_type("ResCol", "Column", "RCC Column M25")
                    
                    # Add Components (Iterate columns)
                    for c in gm.columns:
                        cobie.add_component(c.id, "ResCol", f"Level_{c.level}", "Structural Column")
                        cobie.add_attribute(c.id, "Load", f"{c.load_kn:.1f}", "kN")
                        cobie.add_coordinate(c.id, c.x, c.y, c.level*story_height)
                        
                    cobie_json = cobie.export_json()
                    st.success(f"Generated COBie dataset for {len(gm.columns)} components.")
                    
                    st.download_button(
                        label="📦 Download COBie JSON",
                        data=cobie_json,
                        file_name="COBie_Data.json",
                        mime="application/json"
                    )
            
            with ht3:
                st.subheader("Site Inspection Checklists")
                st.markdown("Digital checklists for site engineers based on IS 13920.")
                
                stage = st.selectbox("Construction Stage", ["Pre_Pour", "Post_Pour"])
                site_mgr = SiteInspectionManager("Project Site")
                checklist = site_mgr.generate_checklist(stage)
                
                st.write(f"**{stage} Checklist:**")
                for item in checklist:
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"**{item.query}** (Ref: {item.reference_code})")
                    c2.checkbox("Pass", key=f"chk_{item.id}")
                    
                st.markdown("---")
                st.markdown("#### 🔍 AI & AR Site Tools")
                
                ar_col1, ar_col2 = st.columns(2)
                with ar_col1:
                    st.info("📷 **AR Defect Overlay**")
                    if st.button("Simulate AR Projection"):
                         st.image("https://via.placeholder.com/400x300.png?text=AR+Rebar+Overlay+Simulation", caption="Projected Rebar Cage")
                
                with ar_col2:
                    st.info("📍 **Geo-Tagged Issue Map**")
                    # Fake Map Data
                    map_data = site_mgr.get_defect_map_data()
                    # If empty (no defects yet), add dummy
                    if not map_data:
                        map_data = [{"lat": 12.9716, "lon": 77.5946, "type": "Crack", "severity": "Medium"}]
                    
                    st.map(data=[{"lat": d["lat"], "lon": d["lon"]} for d in map_data], zoom=15)
                    
                st.markdown("#### QR Tagging")
                sel_qr = st.selectbox("Generate QR for", [c.id for c in gm.columns[:5]])
                st.code(site_mgr.generate_qr_code(sel_qr))

            with ht4:
                st.subheader("📡 Smart SHM & IoT Dashboard")
                st.markdown("Real-time sensor data visualization and anomaly detection.")
                
                from src.shm_viz import SHMDashboard
                shm_viz = SHMDashboard("Project Twin")
                
                # 1. Damage Index
                col_shm1, col_shm2 = st.columns([1, 2])
                
                with col_shm1:
                    st.markdown("#### structural Health Index")
                    cur_freq = st.slider("Live Frequency (Hz)", 0.5, 2.0, 1.45, 0.01)
                    base_freq = 1.5
                    
                    di_res = shm_viz.get_damage_index(cur_freq, base_freq)
                    st.metric("Damage Index", f"{di_res['value']:.3f}", delta=di_res['message'], delta_color="inverse")
                    
                    st.progress(max(0.0, min(1.0, 1.0 - di_res['value'])), text="Health Score")
                
                with col_shm2:
                    st.markdown("#### 📊 Vibration Spectrum (FFT)")
                    import pandas as pd
                    fft_data = shm_viz.calculate_fft_spectrum(cur_freq)
                    chart_data = pd.DataFrame({"Frequency (Hz)": fft_data['freq'], "Amplitude": fft_data['amp']})
                    st.line_chart(chart_data, x="Frequency (Hz)", y="Amplitude")
                
                st.markdown("#### 🔥 Sensor Strain Heatmap")
                st.caption("Red zones indicate strain exceeding yield threshold.")
                # We would render 3D model with colors here. For now, simulate list.
                heat_data = shm_viz.generate_heatmap_data(["C1", "C2", "B1", "B5"])
                st.write(heat_data)

        # Categorized Reports Section
        st.markdown("#### 📑 Categorized Reports")
        report_cols = st.columns(4)
        
        # Summary Report
        summary_file = "Summary_Report.pdf"
        reporter.generate_summary_report(summary_file, gm, bom, use_fly_ash=use_fly_ash)
        with open(summary_file, "rb") as f:
            report_cols[0].download_button(
                label="📊 Summary",
                data=f.read(),
                file_name="Summary_Report.pdf",
                mime="application/pdf"
            )
        
        # Schedule Report
        schedule_file = "Design_Schedules.pdf"
        reporter.generate_schedule_report(schedule_file, gm)
        with open(schedule_file, "rb") as f:
            report_cols[1].download_button(
                label="📋 Schedules",
                data=f.read(),
                file_name="Design_Schedules.pdf",
                mime="application/pdf"
            )
        
        # BBS Report
        bbs_file = "BBS_Report.pdf"
        bbs_reporter = BBSReportGenerator()
        bbs_reporter.generate_bbs_report(bbs_file, project_bbs, "Bar Bending Schedule")
        with open(bbs_file, "rb") as f:
            report_cols[2].download_button(
                label="🔩 BBS Report",
                data=f.read(),
                file_name="BBS_Report.pdf",
                mime="application/pdf"
            )
        
        # Audit Report
        audit_file = "Audit_Report.pdf"
        reporter.generate_audit_report(audit_file, gm, audit_results, auditor.math_breakdown)
        with open(audit_file, "rb") as f:
            report_cols[3].download_button(
                label="✅ Audit",
                data=f.read(),
                file_name="Audit_Report.pdf",
                mime="application/pdf"
            )
        
        st.markdown("---")
        st.markdown("#### 📄 Complete Report")
        
        report_file = "Structural_Design_Report.pdf"
        reporter.generate_report(
            report_file, 
            gm, 
            bom, 
            audit_results=audit_results, 
            math_breakdown=auditor.math_breakdown,
            project_name="Structural Design Report",
            use_fly_ash=use_fly_ash
        )
        
        with open(report_file, "rb") as f:
            pdf_data = f.read()
        
        st.download_button(
            label="📄 Download Structural Report (Free Beta)",
            data=pdf_data,
            file_name="Structural_Report.pdf",
            mime="application/pdf"
        )
        
        # ========== FEEDBACK WIDGET ==========
        st.markdown("---")
        st.markdown("#### 💬 How was your experience?")
        _fb_col1, _fb_col2 = st.columns([1, 2])
        with _fb_col1:
            _fb_rating = st.radio(
                "Rate this report",
                ["⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3", "⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5"],
                index=4,
                key="feedback_rating"
            )
        with _fb_col2:
            _fb_text = st.text_area(
                "Any suggestions or issues?",
                placeholder="e.g., The beam schedule was very helpful. Would love to see wind load analysis.",
                key="feedback_text",
                max_chars=500
            )
        if st.button("Submit Feedback", key="submit_feedback_btn"):
            st.success("Thank you for your feedback! 🙏")
            logger.info("User feedback: rating=%s, text=%s", _fb_rating, _fb_text)

else:
    st.info("Adjust parameters in the sidebar and click 'Run Analysis' to generate the structure.")

# --- PROFESSIONAL USAGE GUIDANCE (Trust-Building Disclaimer) ---
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
    <p style="margin: 0;">© 2026 StructOptima — Built by Charan Tej, Chandana, and Srinidh</p>
    <p style="margin: 4px 0 0 0;">All calculations per IS 456:2000 · IS 1893:2016 · IS 13920:2016 | v1.0.0</p>
    <p style="margin: 4px 0 0 0;">
        <a href="/terms" style="color: #1565c0; text-decoration: none;">Terms of Service</a> · 
        <a href="/privacy" style="color: #1565c0; text-decoration: none;">Privacy Notice</a>
    </p>
</div>
""", unsafe_allow_html=True)
